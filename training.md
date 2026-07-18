# Vision Model Training Pipeline

How the enemy detector gets its data, gets trained (Modal), crosses the bridge (export), gets converted (TensorRT), and runs live (inference on the Jetson).

## Class taxonomy (6 classes)

Every enemy is labeled with **two boxes** — head and body — across three vest variants:

| id | class | notes |
|----|-------|-------|
| 0 | `enemy_body` | general enemy, no vest color |
| 1 | `enemy_head` | |
| 2 | `enemy_blue_body` | blue vest |
| 3 | `enemy_blue_head` | |
| 4 | `enemy_red_body` | red vest |
| 5 | `enemy_red_head` | |

Heads are small targets (often <20px at distance) — this drives the image-count quota up and the input-resolution decision (see Training).

## Image quota (research-verified)

**Target: ~6,000 labeled images (2,000 per vest variant) + ~10% background frames ≈ 6,600 total. Floor for demo-grade: ~1,500. Past ~8-10k, diversity — not count — is the only thing that still moves accuracy.**

Reasoning (from research synthesis):
- The single-class baseline for this closed domain is **~3,500 images ≈ 5-10k instances**: AssaultCube hobby models work at 120-355 images, 2-5k saturates a fixed art style, and Ultralytics' production bar (1.5k imgs / 10k instances per class) is met via multi-enemy frames. Our 6-class taxonomy (3 vest colors × head/body) roughly doubles that to ~6k, balanced **≥2,000 images per vest variant** (spawn-force each variant when recording).
- Every enemy contributes a body **and** head instance, so 6k images at 1-3 enemies/frame yields ~10-25k instances per body class and the same for heads.
- **~10% background/confuser frames** (no enemies; include corpses, teammates, pickups, muzzle flash) to kill false positives.
- Diversity beats volume: **8 maps × ~800 kept frames** (indoor/outdoor, bright/dark/fog), bot counts 2-8, oversample distant enemies (10-20px), crouching/jumping/partial occlusion, capture during real combat.
- **Subsample by motion, not fixed rate:** keep a frame only if ≥0.3s elapsed AND (view yaw changed >10° OR any enemy box moved >20px). Fixed-fps subsampling still produces near-duplicate clones.
- Labels are auto-generated and perfect, so this is ~1-2 hours of scripted bot matches; training cost is ~$0.50/run on Modal either way.

## 1. Data generation (Jetson, no ML)

The patched AssaultCube emits ground-truth enemy screen-space boxes (head + body, with vest color) over UDP each frame.

1. Collector script captures the screen (`mss` ≥10.2 on DISPLAY=:1) and listens on the telemetry UDP port.
2. **Tick-match** each kept frame to its telemetry packet (never "latest packet" — during flicks that shifts boxes by tens of pixels and silently poisons the dataset).
3. Telemetry hook rules: drop fully-occluded enemies (engine reports through walls — training on them teaches the model to hallucinate on empty walls); keep partially-occluded only if ≥~40% visible; clip boxes to screen; drop boxes <4px wide; validate 0≤coords≤1; corpses = negative, consistently.
4. Write YOLO format: `images/xxx.png` + `labels/xxx.txt` (one line per box: `class cx cy w h` normalized; empty txt = background frame). Motion-based subsample rule from the quota section; rotate maps and force vest variants to hit per-class balance.
5. **Eyeball 50-100 random labeled frames before spending any GPU time** — a systematic box offset poisons everything downstream.
6. Split **by map, never random frames**: 6 maps train / 1 val / 1 test (~70/20/10). Random splits leak near-duplicates and give 0.99 mAP on a model that fails live.
7. `data.yaml` with absolute `path:` (ultralytics rewrites relative paths) + 6 class names. **Tar the dataset** (one file — Modal Volumes degrade past ~50k files) and `modal volume put`.

## 2. Model training (Modal)

- **Model (research-verified):** **YOLO26n** primary — only family with measured Orin Nano numbers (~4.6ms FP16), NMS-free head (near-zero postprocess, clean TensorRT 10.3 graph), small-object losses (ProgLoss/STAL) that target exactly our distant-enemy case. Fallback: **YOLO26s** (same pipeline, ~+4ms). Safety net: **YOLO11n** (all FPS-aimbot prior art shipped small YOLOs; nobody ships DETRs on edge). Verify `YOLO("yolo26n.pt")` loads on latest ultralytics before training.
- **Where:** Modal serverless GPU — **`gpu="A10"`** ($1.10/hr; A100 buys nothing for a nano model, dataloading is the bottleneck). **~15-40 min, ~$0.30-0.50 per run**; fits free starter credits. Launch 26n and 26s as parallel `.spawn()` runs, pick by on-device latency + distant-enemy recall.
  ```python
  @app.function(gpu="A10", cpu=8, memory=32768, timeout=4*60*60, volumes={"/vol": volume})
  def train(epochs=60, model_size="yolo26n.pt", run_name="run1"):
      from ultralytics import YOLO
      model = YOLO(model_size)                      # COCO-pretrained
      model.train(
          data="/vol/dataset/data.yaml", epochs=epochs, imgsz=640,
          batch=0.95, workers=8, close_mosaic=10, fliplr=0.5,
          hsv_h=0.01, hsv_s=0.3, hsv_v=0.3,         # halved: renderer palette is fixed; vest COLOR is class signal
          degrees=0, patience=15, cache="ram",
          project="/vol/runs", name=run_name, exist_ok=True)
  ```
  Modal image: `debian_slim` + `apt libgl1 libglib2.0-0` + pip `ultralytics opencv-python-headless onnx onnxslim onnxruntime`, env `WANDB_MODE=disabled`.
- **Input resolution:** 640px baseline. If distant-head recall lags on val, retrain at **imgsz=1024** (~2.5x latency, still in budget) before anything fancier.
- **Judge it on:** per-class mAP@50 and recall on the held-out map (expect >0.95 overall on an honest split). Heads will lag bodies — bodies gate the trigger, heads are the aim-assist bonus.
- **Caution for our taxonomy:** the halved HSV augmentation matters — vest *color* distinguishes 4 of our 6 classes, so aggressive hue augmentation would destroy the blue/red signal.

## 3. The bridge (export)

The Jetson's PyTorch is CPU-only, so PyTorch never runs inference on device. On Modal (or any machine with the venv):

```python
model = YOLO("best.pt")
model.export(format="onnx", imgsz=640, opset=17, simplify=True, dynamic=False, batch=1)
```

Do this inside the Modal function (no `format="engine"` — TensorRT engines are device-specific, and ultralytics engine export requires CUDA torch anyway). ONNX is the portable handoff. Pull with `modal volume get`, then `scp best.onnx shortai:~/models/`. Verify the ONNX output tensor shape after export — YOLO26's NMS-free head differs from the `(1, 5+nc, 8400)` v8/11 layout; write the decode against what trtexec reports.

## 4. Conversion (Jetson, TensorRT)

TensorRT engines are hardware-specific — **must be built on the Orin Nano itself** (TensorRT 10.3, one-time ~2-5 min):

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks   # pinned clocks: without this, 30-40% slower + governor jitter
/usr/src/tensorrt/bin/trtexec --onnx=best.onnx --saveEngine=best_fp16.engine --fp16 --memPoolSize=workspace:2048
```

trtexec's summary prints the first ground-truth latency number.
- **FP16**: yes, always — ~2x speedup, negligible accuracy loss.
- **INT8**: skip — needs calibration data + GPU torch, saves ~1ms, costs ~3 mAP, has open accuracy bugs.

## 5. Inference (Jetson, live loop)

Per-frame loop, all Python, in a venv:

**Hard constraint (verified):** ultralytics `.engine` inference requires CUDA torch — impossible with the Jetson's CPU-only torch. The runtime is raw **TensorRT 10 Python bindings** (`execute_async_v3` + `set_tensor_address`; the old bindings API is gone in TRT 10) with `cuda-python` for buffers. Cap the game at `maxfps 60` so it doesn't spin the shared iGPU to 100% and blow tail latency.

1. **Capture** — `mss` 10.2 (XShm) grabs the 1024x768 game window from DISPLAY=:1 — **measured ~18ms, the dominant cost**; crop the capture region tighter if more FPS is ever needed.
2. **Preprocess** — OpenCV (`cv2.setNumThreads(2)`): letterbox to 640, BGR→RGB, /255, NCHW (~3.8ms measured).
3. **Infer** — TRT engine FP16: 4.2ms standalone, **~9.5ms measured with the game contending for GPU**. H2D ~0.9ms.
4. **Decode** — yolo26 exports an NMS-free end-to-end head: output `(1, 300, 6)` rows of `[x1,y1,x2,y2,conf,cls]` in letterboxed coords — decode is confidence-filter + un-letterbox (~1.3ms).
5. **Decide** — `enemy_*_head` or `enemy_*_body` box overlapping crosshair (screen center) above ~0.4 confidence → FIRE.
6. **Send** — one raw UDP packet to the Genesis Mini (`{channel, burst_ms}`); firmware enforces max burst + cooldown + 500ms watchdog.

**Loop: ~34ms end-to-end measured with game live → ~30Hz** (48 FPS without the game) — inside the muscle's ~150ms electromechanical delay, which dominates anyway. Memory fine on 8GB unified.

**Validated on-device (2026-07-18):** venv `~/vision-venv`, engine `~/models/yolo26n_fp16.engine`, test harness `~/vision/infer_test.py`, docs `~/vision/README.md`. Gotcha: **pin `cuda-python==12.6.*`** — 13.x fails with `cudaErrorInsufficientDriver` on JetPack 6.2.1. `maxfps` is an in-game cvar, not a CLI flag (game vsyncs at 60 anyway). GNOME idle-lock was disabled so unattended captures don't hit the lock screen. Swapping in the fine-tuned 6-class model changes nothing structurally: yolo26 output stays `(1,300,6)` for any class count — re-export ONNX, rebuild engine on-device, replace class names.

**Fallback tier:** the telemetry hook's ground-truth boxes plug into step 5 directly — identical downstream chain, so the demo works even with no model.
