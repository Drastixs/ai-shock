# Modal training

## One-time setup (needs you, ~2 min)
1. Account at https://modal.com (GitHub login; starter plan includes $30/mo free credits — a training run costs ~$0.30-0.50).
2. `pip install modal` (any local python/venv)
3. `modal setup` — opens a browser to mint the auth token. Interactive, so run it yourself (type `! modal setup` in the Claude prompt to run it in-session).

## Smoke test
```
modal run modal/test_modal.py
```
Passes = auth works, A10 GPU comes up, CUDA visible, yolo26n loads + infers on GPU, the `yolo-assaultcube` volume is writable. Ends with `SMOKE TEST PASSED — ready to train`.

## Training (once the Jetson collector has produced ~/dataset)
```
# Jetson -> Mac -> Modal volume
ssh shortai 'tar cf /tmp/dataset.tar -C ~/dataset .' && scp shortai:/tmp/dataset.tar .
modal volume put yolo-assaultcube dataset.tar /dataset.tar

# Train (~15-40 min on A10). Run 26n and 26s in parallel terminals if desired.
modal run modal/train_yolo.py --run-name run1
modal run modal/train_yolo.py --model-size yolo26s.pt --run-name run1-s

# Fetch best.pt + best.onnx, push ONNX to the Jetson, rebuild engine there
modal volume get yolo-assaultcube /runs/run1/weights ./weights
scp weights/best.onnx shortai:~/models/
ssh shortai '/usr/src/tensorrt/bin/trtexec --onnx=$HOME/models/best.onnx --saveEngine=$HOME/models/best_fp16.engine --fp16 --memPoolSize=workspace:2048'
```

Notes: `data.yaml` inside the tar must use absolute `path: /vol/dataset`. Never export `format="engine"` on Modal — TensorRT engines are device-specific, build on the Jetson. Details/rationale: ../training.md
