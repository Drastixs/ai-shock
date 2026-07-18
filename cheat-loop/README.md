# cheat-loop

The real-time loop that plays Assault Cube through the wearer's arm. Full design
and rationale: [`loop-design.md`](loop-design.md).

```
source.read() -> Frame -> select() -> decide() -> stim.send()  (~30 Hz)
```

One `Frame` (list of screen-pixel `Detection`s) flows through fixed SELECT /
DECIDE / STIM stages. The `Frame` comes from either the **vision** model or the
game's **telemetry** — same format, so the whole loop is source-agnostic.

## Files
| File | Role |
|------|------|
| `loop.py` | entrypoint — wires the stages, timing, overlay |
| `config.py` | every tunable (ports, thresholds, channels, timing) |
| `types_.py` | `Detection` / `Frame` / `StimCommand` + box helpers |
| `telemetry.py` | `TelemetrySource` — ground-truth boxes over UDP (no ML) |
| `vision.py` | `VisionSource` — mss + TensorRT YOLO26 (Jetson only) |
| `target.py` | `select()` + `decide()` — pure logic, unit-tested |
| `stim.py` | `StimClient` — UDP out + burst clamp + cooldown |
| `overlay.py` | draws boxes / crosshair / FIRE for the demo |
| `test_target.py` | 9 synthetic-frame decision tests, no hardware |

## Run

```bash
# Pure logic tests — no hardware, anywhere:
python3 test_target.py

# Full loop on ground-truth boxes, printing decisions, no ESP32 (laptop/Jetson):
python3 loop.py --source telemetry --dry-run

# Demo tier 2 — telemetry -> real ESP32, no ML:
python3 loop.py --source telemetry

# Demo tier 3 (headline) — vision model -> real ESP32 (on the Jetson):
DISPLAY=:1 ~/vision-venv/bin/python loop.py --source vision --show
```

Flags: `--nudge` (L/R aim-assist, stretch), `--show` (overlay window), `--n N`
(stop after N iterations), `--conf`, `--engine`.

## Deploy to the Jetson
```bash
scp -r cheat-loop shortai:~/
# vision path uses ~/vision-venv (tensorrt, cuda-python==12.6.*, cv2, mss)
```

The vision runtime mirrors the validated `~/vision/infer_test.py`. Telemetry needs
the game running with `telemetry 1` (emits to `127.0.0.1:28786`).

## Safety
The loop is the *second* safety layer; the ESP32 firmware is authoritative. Loop
side: burst clamp (`max_burst_ms`), per-channel cooldown (`cooldown_ms`), and
every failure path (no boxes / stale socket / dead process / WiFi drop) degrades
to no-UDP → firmware watchdog opens the relays. See `loop-design.md` §5, §10 and
the project safety invariants in `../CLAUDE.md`.
