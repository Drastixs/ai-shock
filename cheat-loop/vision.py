"""VisionSource — the ML detection path (loop-design.md §2a).  [Jetson only]

mss screen grab -> letterbox 640 -> TensorRT 10 FP16 engine -> decode -> Frame in
screen pixels. The TRT runner and pre/post-processing are lifted verbatim from
the validated ~/vision/infer_test.py so the two stay in lock-step.

Requires tensorrt, cuda-python (==12.6.* on JetPack 6.2.1), cv2, mss -- imported
lazily so the rest of cheat-loop runs on a laptop without them.

Run standalone (on the Jetson) to sanity-check detections:
  DISPLAY=:1 ~/vision-venv/bin/python vision.py --n 100
"""

import os

import numpy as np

from types_ import Detection, Frame


def _check(err):
    from cuda.bindings import runtime as cudart
    code, rest = (err[0], err[1:]) if isinstance(err, tuple) else (err, ())
    if code != cudart.cudaError_t.cudaSuccess:
        raise RuntimeError(f"CUDA error: {code}")
    return rest[0] if len(rest) == 1 else rest


class TRTModel:
    """Minimal TensorRT 10 runner (execute_async_v3 + set_tensor_address)."""

    def __init__(self, engine_path):
        import tensorrt as trt
        from cuda.bindings import runtime as cudart
        self._cudart = cudart

        logger = trt.Logger(trt.Logger.WARNING)
        with open(os.path.expanduser(engine_path), "rb") as f:
            self.engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()
        self.stream = _check(cudart.cudaStreamCreate())

        self.inputs, self.outputs = [], []
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            shape = tuple(self.engine.get_tensor_shape(name))
            dtype = np.dtype(trt.nptype(self.engine.get_tensor_dtype(name)))
            host = np.empty(shape, dtype=dtype)
            dptr = _check(cudart.cudaMalloc(host.nbytes))
            self.context.set_tensor_address(name, int(dptr))
            entry = (name, shape, dtype, host, dptr)
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
                self.inputs.append(entry)
            else:
                self.outputs.append(entry)

    def __call__(self, x):
        """Run one forward pass on preprocessed input x, return {name: ndarray}."""
        cudart = self._cudart
        name, shape, dtype, host, dptr = self.inputs[0]
        src = np.ascontiguousarray(x, dtype=dtype)
        _check(cudart.cudaMemcpyAsync(
            dptr, src.ctypes.data, src.nbytes,
            cudart.cudaMemcpyKind.cudaMemcpyHostToDevice, self.stream))
        _check(cudart.cudaStreamSynchronize(self.stream))
        if not self.context.execute_async_v3(self.stream):
            raise RuntimeError("execute_async_v3 failed")
        _check(cudart.cudaStreamSynchronize(self.stream))
        outs = {}
        for name, shape, dtype, host, dptr in self.outputs:
            _check(cudart.cudaMemcpyAsync(
                host.ctypes.data, dptr, host.nbytes,
                cudart.cudaMemcpyKind.cudaMemcpyDeviceToHost, self.stream))
            outs[name] = host
        _check(cudart.cudaStreamSynchronize(self.stream))
        return outs


def letterbox(img, size, color=114):
    import cv2
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    top, left = (size - nh) // 2, (size - nw) // 2
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), color, dtype=np.uint8)
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, r, left, top


def preprocess(frame_bgr, size):
    import cv2
    lb, r, dx, dy = letterbox(frame_bgr, size)
    x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = np.expand_dims(x.transpose(2, 0, 1), 0)  # (1,3,size,size)
    return np.ascontiguousarray(x), r, dx, dy


def decode(outputs, r, dx, dy, conf_thres):
    """TRT outputs -> [Detection] in original-frame pixels.

    Handles the yolo26 NMS-free head (1,300,6)=[x1,y1,x2,y2,conf,cls] and a
    v8/11 raw head (1,4+nc,8400) as a fallback (see infer_test.py).
    """
    out = next(iter(outputs.values()))
    dets = []
    if out.ndim == 3 and out.shape[2] == 6:
        for x1, y1, x2, y2, conf, cls in out[0]:
            if conf < conf_thres:
                continue
            dets.append(Detection(int(cls), (x1 - dx) / r, (y1 - dy) / r,
                                  (x2 - dx) / r, (y2 - dy) / r, float(conf)))
    elif out.ndim == 3 and out.shape[1] >= 5:
        import cv2
        p = out[0]
        scores = p[4:]
        cls_ids, confs = scores.argmax(0), scores.max(0)
        keep = confs >= conf_thres
        boxes, kconf, kcls = [], [], []
        for i in np.flatnonzero(keep):
            cx, cy, w, h = p[:4, i]
            boxes.append([cx - w / 2, cy - h / 2, w, h])
            kconf.append(float(confs[i]))
            kcls.append(int(cls_ids[i]))
        for i in cv2.dnn.NMSBoxes(boxes, kconf, conf_thres, 0.45):
            i = int(i)
            bx, by, bw, bh = boxes[i]
            dets.append(Detection(kcls[i], (bx - dx) / r, (by - dy) / r,
                                  (bx + bw - dx) / r, (by + bh - dy) / r, kconf[i]))
    else:
        raise ValueError(f"unrecognized output shape {out.shape}")
    return dets


class VisionSource:
    def __init__(self, cfg):
        import mss
        self.cfg = cfg
        self.model = TRTModel(cfg.engine())
        self.sct = mss.mss()
        self.mon = self.sct.monitors[1]
        # warmup (not timed) so the first real frame isn't slow
        for _ in range(5):
            self.read()

    def grab(self):
        raw = np.asarray(self.sct.grab(self.mon))
        return np.ascontiguousarray(raw[:, :, :3])  # BGRA -> BGR

    def read(self, img=None):
        frame_bgr = img if img is not None else self.grab()
        x, r, dx, dy = preprocess(frame_bgr, self.cfg.img_size)
        outs = self.model(x)
        dets = decode(outs, r, dx, dy, self.cfg.conf_thres)
        h, w = frame_bgr.shape[:2]
        return Frame(w, h, dets, frame_bgr)

    def close(self):
        self.sct.close()
