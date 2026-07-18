# Modal smoke test — verifies the exact stack train_yolo.py needs.
# Run:  modal run modal/test_modal.py
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .uv_pip_install("ultralytics", "opencv-python-headless", "onnx", "onnxslim", "onnxruntime")
    .env({"WANDB_MODE": "disabled"})
)
volume = modal.Volume.from_name("yolo-assaultcube", create_if_missing=True)
app = modal.App("smoke-test", image=image)


@app.function(timeout=120)
def hello() -> str:
    import platform
    return f"CPU container OK: python {platform.python_version()} on {platform.machine()}"


@app.function(gpu="A10", timeout=600, volumes={"/vol": volume})
def gpu_smoke() -> dict:
    import subprocess, time
    import numpy as np
    import torch
    from ultralytics import YOLO

    out = {}
    out["gpu"] = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True,
    ).stdout.strip()
    out["torch_cuda"] = torch.cuda.is_available()

    # Tiny end-to-end: load yolo26n (downloads ~5MB weights), run one GPU inference.
    model = YOLO("yolo26n.pt")
    t = time.time()
    res = model(np.zeros((640, 640, 3), dtype=np.uint8), device=0, verbose=False)
    out["yolo26n_infer_ms"] = round((time.time() - t) * 1000, 1)
    out["yolo26n_loaded"] = res is not None

    # Volume round-trip (same volume the dataset will live on).
    with open("/vol/.smoke_test", "w") as f:
        f.write("ok")
    volume.commit()
    volume.reload()
    out["volume_rw"] = open("/vol/.smoke_test").read() == "ok"
    return out


@app.local_entrypoint()
def main():
    print(hello.remote())
    r = gpu_smoke.remote()
    for k, v in r.items():
        print(f"  {k}: {v}")
    ok = r["torch_cuda"] and r["yolo26n_loaded"] and r["volume_rw"]
    print("\nSMOKE TEST PASSED — ready to train" if ok else "\nSMOKE TEST FAILED — see above")
