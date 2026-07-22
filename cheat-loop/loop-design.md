# The Cheat Loop — Full Design

The real-time loop that runs on the Jetson Orin Nano ("ShortAi") and plays
Assault Cube *through the wearer's arm*. It looks at the screen, finds enemies,
picks the one nearest the crosshair, and fires the trigger muscle when the
crosshair is over an enemy.

This document is the authoritative plan. The code in this directory implements
exactly this. Read it top-to-bottom to understand the whole loop.

---

## 0. The loop in one breath

```
             ┌──────────────── one iteration (~34 ms, ~30 Hz) ────────────────┐
  screen ──► CAPTURE ──► DETECT ──► SELECT ──► DECIDE ──► STIM ──► (wearer's arm)
             (mss)       (boxes)    (nearest)  (fire?)    (UDP)
```

Every iteration produces the same intermediate object regardless of where the
boxes came from: a `Frame` = a list of `Detection(cls, x1, y1, x2, y2, conf)`
in **screen pixels**, plus the frame size `(w, h)`. Everything downstream of
DETECT is source-agnostic.

There are **two interchangeable DETECT sources** that emit that identical
`Frame`:

| Source | How it gets boxes | When we use it | ML? |
|--------|-------------------|----------------|-----|
| **VisionSource** | `mss` grabs the screen → TensorRT YOLO26 → decode | The headline demo | yes |
| **TelemetrySource** | reads the patched game's UDP ground-truth boxes | Fallback / no-model demo / bring-up | no |

Because both emit the same `Frame`, **SELECT / DECIDE / STIM never change.** You
flip one flag (`--source vision|telemetry`) and the rest of the loop is byte-for
-byte identical. That is the whole architectural trick: the ML is a swappable
front-end on a fixed control loop.

---

## 1. CAPTURE — get the pixels

**Default: `mss` screen grab of `DISPLAY=:1`.** Already validated on-device at
**~18 ms**, the single dominant cost in the loop. Grabs the 1024×768 game
window. No game patch required.

```python
raw   = np.asarray(sct.grab(mon))        # BGRA
frame = np.ascontiguousarray(raw[:, :, :3])  # BGRA -> BGR (this is the "RGB conversion")
```

The "load into memory / RGB conversion" step the brief mentions is exactly this
slice: mss hands back a `BGRA` buffer; we drop the alpha to get `BGR` (OpenCV's
native order), then preprocessing does `BGR→RGB` for the model. No extra copy
beyond `ascontiguousarray`.

**Optional optimization (do NOT build yet):** patch AC to publish its GL
framebuffer into POSIX shared memory each frame, so the loop `memcpy`s instead of
round-tripping through X/mss. Could shave ~15 ms. The hook scaffolding already
exists in the source (`telemetrycapture` does frame-exact framebuffer capture for
training). We keep mss because it is proven and the loop is already inside the
muscle's reaction time — capture speed is not the bottleneck that matters.

**TelemetrySource path skips CAPTURE for detection** (it gets boxes from UDP),
but the loop still grabs a frame *for the on-screen overlay* so the demo shows
what the loop "sees."

---

## 2. DETECT — pixels (or UDP) → boxes

### 2a. VisionSource (the ML path)
Lifted from the validated `~/vision/infer_test.py`:

1. **Preprocess** — `cv2` letterbox to 640, `BGR→RGB`, `/255`, `HWC→NCHW`,
   contiguous `float32 (1,3,640,640)`. ~3.8 ms.
2. **Infer** — TensorRT 10 FP16 engine via raw bindings (`execute_async_v3` +
   `set_tensor_address`, `cuda-python` buffers — ultralytics `.engine` needs CUDA
   torch, which the Jetson does not have). ~9.5 ms with the game contending.
3. **Decode** — YOLO26 NMS-free head, output `(1, 300, 6)` =
   `[x1,y1,x2,y2,conf,cls]` in letterbox coords. Filter by `conf ≥ CONF_THRES`,
   un-letterbox back to screen pixels. ~1.3 ms.

Classes: `0 = enemy` (body), `1 = head`. (The engine was trained with the 2-class
remap; see `../docs/training.md`.)

### 2b. TelemetrySource (the ground-truth path)
Bind a UDP socket to `127.0.0.1:28786`. Each datagram is one frame:

```json
{"ms": 123456, "w": 1024, "h": 768,
 "boxes": [[0, x1,y1,x2,y2], [1, x1,y1,x2,y2], ...]}
```

Box format is `[class, x1, y1, x2, y2]` (class first, screen pixels, top-left
origin). Classes 0–5 in the raw hook (colour variants); we **remap on read**
`0/2/4 → 0 enemy`, `1/3/5 → 1 head` — same remap as training, so classes match
the vision path exactly. Confidence is synthesized as `1.0` (ground truth).

The hook only emits enemies ≥40% visible and never emits the bot the camera
rides — so its boxes are already "what a fair player can see." No occlusion
filtering needed downstream.

**Freshness rule:** keep only the newest datagram each iteration (drain the
socket non-blocking). Never act on a stale packet — during a flick the boxes move
tens of pixels per frame. If the newest packet is older than `STALE_MS`, treat as
"no detections" (fail safe → no fire).

---

## 3. SELECT — pick the target

Input: the `Frame`'s detections. The crosshair is the **screen center**
`(w/2, h/2)` — AssaultCube renders the crosshair dead-center.

```
crosshair = (w/2, h/2)
for each detection d:
    d.center = ((x1+x2)/2, (y1+y2)/2)
    d.dist   = hypot(d.center.x - crosshair.x, d.center.y - crosshair.y)
    d.covers = (x1 <= crosshair.x <= x2) and (y1 <= crosshair.y <= y2)
```

**Target = the detection whose center is nearest the crosshair**, above
`CONF_THRES`. Two refinements:

- **Head preference:** if a `head` and an `enemy` box overlap the crosshair in
  the same region, prefer the `head` as the *aim* target (heads are the aim
  bonus). For *firing*, either class counts — crosshair over any enemy fires.
- **Ignore tiny boxes** (`< MIN_BOX_PX` wide) — distant noise the trigger
  shouldn't chase.

Output: `target` (nearest detection) or `None`.

> The brief's "move to the nearest respective one to the center of the screen" =
> this stage. We select the nearest target; whether we *move the aim* toward it
> (stretch, §4b) or just *fire when it's already centered* (the money shot, §4a)
> is the DECIDE stage's job.

---

## 4. DECIDE — fire? / nudge?

### 4a. FIRE (the money shot — primary, always on)
```
if target and target.covers and target.conf >= FIRE_CONF:
    fire(TRIGGER_CHANNEL)
```
Crosshair is inside an enemy/head box → pull the trigger. That's it. This is the
demo headline and it needs no aim control at all — the wearer sweeps their own
aim, the loop fires the instant the crosshair crosses an enemy.

**Latency accounting** (why we don't need prediction for the money shot):
relay pull-in ≈70 ms + muscle electromechanical delay ≈150 ms ≈ **~220 ms** from
UDP-send to finger-move. For a crosshair that is *already over* the enemy, that's
fine. Leading a moving target would need prediction — explicitly out of scope.

### 4b. NUDGE (aim-assist L/R — stretch goal, behind `--nudge`)
```
dx = target.center.x - crosshair.x           # +right, -left
if abs(dx) > NUDGE_DEADZONE_PX:
    fire(RIGHT_CHANNEL if dx > 0 else LEFT_CHANNEL, burst=nudge_burst(dx))
```
Bicep/tricep (or wrist) stim rotates the aim toward the target. Horizontal only;
**up/down is out of scope** (CLAUDE.md). This is gated off by default — it needs
per-wearer muscle mapping and a solid-state relay for timing precision (see
`relay-timings.md`). Ship the money shot first.

### DECIDE is pure
The decision stage takes a `Frame` + config and returns a list of
`StimCommand(channel, burst_ms)` (usually 0 or 1). No I/O. This makes it trivially
testable with recorded frames — feed telemetry captures in, assert the commands
out.

---

## 5. STIM — send it, safely

One raw UDP datagram to the Genesis Mini SoftAP: `{"ch": <n>, "ms": <burst>}`
(compact JSON; firmware also accepts the binary form if we optimize later).

The loop is the **second** layer of the safety envelope; the firmware is the
first and authoritative one (it can't trust the network):

| Guard | Enforced by | Value |
|-------|-------------|-------|
| Normally-open relays (fail-off) | hardware | — |
| No-packet watchdog → all relays open | firmware | 500 ms |
| Max burst per fire | firmware **and** loop | ~300 ms |
| Forced cooldown between bursts | firmware **and** loop | e.g. 300 ms |
| Current never crosses chest | wiring | — |
| Physical kill switch | wearer | — |

Loop-side guards (defensive, firmware is the real gate):
- **Min inter-fire interval** per channel — the loop refuses to send a new fire
  to a channel that fired < `COOLDOWN_MS` ago. Prevents machine-gunning a relay
  (and a muscle) if detections flicker.
- **Burst clamp** — `burst_ms = min(requested, MAX_BURST_MS)`.
- **No keepalive needed:** idle = no packets = watchdog opens relays = stim off,
  which is the safe state. We only ever send *to fire*. (Contrast: if we ever
  hold a relay closed >500 ms we'd need heartbeats — we never do; bursts ≤300 ms.)

---

## 6. Data types (the contract between stages)

```python
Detection = namedtuple("Detection", "cls x1 y1 x2 y2 conf")   # screen pixels
Frame     = namedtuple("Frame", "w h dets img")   # img optional (overlay only)
StimCommand = namedtuple("StimCommand", "channel burst_ms")
```

- **Source** (VisionSource | TelemetrySource): `.read() -> Frame`
- **select(frame, cfg) -> Detection | None**
- **decide(frame, cfg) -> list[StimCommand]**
- **StimClient.send(cmd)** — UDP out, applies cooldown + clamp

---

## 7. Config (all tunables in one place — `config.py`)

```
# capture
DISPLAY            = ":1"
# detection
ENGINE_PATH        = "~/models/yolo26n_fp16.engine"
IMG_SIZE           = 640
CONF_THRES         = 0.40      # decode floor
FIRE_CONF          = 0.40      # confidence needed to pull the trigger
TELEMETRY_ADDR     = ("127.0.0.1", 28786)
STALE_MS           = 100       # ignore telemetry packets older than this
# select / decide
MIN_BOX_PX         = 8         # ignore boxes narrower than this
NUDGE_DEADZONE_PX  = 40
# stim output
STIM_ADDR          = ("192.168.4.1", 4210)   # Genesis Mini SoftAP
TRIGGER_CHANNEL    = 1
LEFT_CHANNEL       = 2
RIGHT_CHANNEL      = 3
FIRE_BURST_MS      = 120       # trigger pulse length
MAX_BURST_MS       = 300       # hard clamp (mirrors firmware)
COOLDOWN_MS        = 300       # min gap between fires on a channel
```

Every magic number lives here so the demo can be tuned live without touching
logic.

---

## 8. Module layout (this directory)

```
cheat-loop/
  loop-design.md   ← this file
  config.py        ← all tunables (§7)
  types.py         ← Detection / Frame / StimCommand (§6)
  vision.py        ← TRTModel + VisionSource (§2a)  [runs on Jetson]
  telemetry.py     ← TelemetrySource (§2b)
  target.py        ← select() + decide() (§3, §4)  [pure, unit-testable]
  stim.py          ← StimClient: UDP + cooldown + clamp (§5)
  loop.py          ← wires it all + overlay + timing (the entrypoint)
  overlay.py       ← draw boxes/crosshair/FIRE for the demo screen
  test_target.py   ← feed synthetic frames, assert decisions (no hardware)
```

The vision runtime (`TRTModel`) is factored out of the existing
`~/vision/infer_test.py` so the two stay in sync. `cheat-loop/` is the canonical
home; deploy to the Jetson with `scp -r cheat-loop shortai:~/`.

---

## 9. Bring-up order (each step independently demoable, commit each)

1. **`config.py` + `types.py`** — the contract. Nothing runs yet.
2. **`telemetry.py` + `target.py` + `stim.py` + `loop.py --source telemetry
   --dry-run`** — full loop on ground-truth boxes, printing decisions, no
   hardware. Proves SELECT/DECIDE end-to-end on the laptop.
3. **`--source telemetry` (live, to real ESP32)** — Demo tier 2 from CLAUDE.md:
   game telemetry → stim fires when enemy under crosshair. No ML.
4. **`vision.py` + `--source vision`** — Demo tier 3, the headline: model
   replaces telemetry, everything downstream unchanged.
5. **`overlay.py`** — on-screen bounding boxes + "FIRE" flash for the money shot.
6. **`--nudge`** — stretch: L/R aim-assist.

---

## 10. Failure modes → all fail to "no stim"

| Failure | Result |
|---------|--------|
| Model crashes / no boxes | no target → no fire |
| Telemetry socket silent | stale → no detections → no fire |
| Loop process dies | no UDP → firmware watchdog opens relays (500 ms) |
| WiFi drop to ESP32 | same watchdog |
| Detection flicker | cooldown throttles to ≤1 fire / COOLDOWN_MS |
| Low confidence | below FIRE_CONF → no fire |

Every path degrades to relays-open = stim-off. The safe state is the default
state.
