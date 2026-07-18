# Train the 6-class AssaultCube enemy detector on Modal.
#
# One-time: upload the dataset tar (created by the Jetson collector) to the volume:
#   tar cf dataset.tar -C ~/dataset .            # on the Jetson, then scp to Mac
#   modal volume put yolo-assaultcube dataset.tar /dataset.tar
# Train:
#   modal run modal/train_yolo.py                          # yolo26n, 60 epochs
#   modal run modal/train_yolo.py --model-size yolo26s.pt --run-name run1-s
# Fetch results:
#   modal volume get yolo-assaultcube /runs/<run_name>/weights ./weights
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .uv_pip_install("ultralytics", "opencv-python-headless", "onnx", "onnxslim", "onnxruntime")
    .env({"WANDB_MODE": "disabled"})
)
volume = modal.Volume.from_name("yolo-assaultcube", create_if_missing=True)
app = modal.App("yolo-assaultcube", image=image)


@app.function(gpu="A10", cpu=8, memory=32768, timeout=4 * 60 * 60, volumes={"/vol": volume})
def train(epochs: int = 60, model_size: str = "yolo26n.pt", run_name: str = "run1") -> str:
    import os, subprocess
    from ultralytics import YOLO

    if not os.path.exists("/vol/dataset/data.yaml"):
        assert os.path.exists("/vol/dataset.tar"), "dataset.tar missing — see header for `modal volume put`"
        os.makedirs("/vol/dataset", exist_ok=True)
        subprocess.run(["tar", "xf", "/vol/dataset.tar", "-C", "/vol/dataset"], check=True)
        volume.commit()

    model = YOLO(model_size)  # COCO-pretrained
    model.train(
        data="/vol/dataset/data.yaml",   # data.yaml must use absolute path: /vol/dataset
        epochs=epochs,
        imgsz=640,                       # bump to 1024 only if distant-head recall lags
        batch=0.95,
        workers=8,
        seed=117,
        close_mosaic=10,
        fliplr=0.5,
        # Halved color aug: renderer palette is fixed AND vest color IS the class signal.
        hsv_h=0.01, hsv_s=0.3, hsv_v=0.3,
        degrees=0,
        patience=15,
        cache="ram",
        project="/vol/runs",
        name=run_name,
        exist_ok=True,
    )

    best = f"/vol/runs/{run_name}/weights/best.pt"
    YOLO(best).export(format="onnx", imgsz=640, opset=17, simplify=True, dynamic=False, batch=1)
    volume.commit()
    return best


@app.local_entrypoint()
def main(epochs: int = 60, model_size: str = "yolo26n.pt", run_name: str = "run1"):
    best = train.remote(epochs=epochs, model_size=model_size, run_name=run_name)
    print(f"done: {best}")
    print(f"fetch: modal volume get yolo-assaultcube /runs/{run_name}/weights ./weights")
