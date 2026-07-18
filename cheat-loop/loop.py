"""The cheat loop — entrypoint that wires every stage together (loop-design.md §0).

  source.read() -> Frame -> select() (for overlay) -> decide() -> stim.send()

The source is the ONLY thing that changes between the ML demo and the no-ML
fallback; SELECT/DECIDE/STIM are identical either way.

Examples
--------
  # No hardware, ground-truth boxes, just print decisions (laptop or Jetson):
  python3 loop.py --source telemetry --dry-run

  # Live telemetry -> real ESP32 (Demo tier 2, no ML):
  python3 loop.py --source telemetry

  # Headline demo: vision model -> real ESP32 (Jetson):
  DISPLAY=:1 ~/vision-venv/bin/python loop.py --source vision

Flags: --nudge (L/R aim-assist), --show (overlay window), --n N (stop after N
iterations, else run forever), --conf, --engine.
"""

import argparse
import signal
import statistics
import time

import target as target_mod
from config import CFG


def build_source(args):
    if args.source == "telemetry":
        from telemetry import TelemetrySource
        return TelemetrySource(CFG), False   # (source, grabs_own_frame)
    from vision import VisionSource
    return VisionSource(CFG), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["vision", "telemetry"], default="telemetry")
    ap.add_argument("--dry-run", action="store_true", help="don't send UDP to the ESP32")
    ap.add_argument("--nudge", action="store_true", help="enable L/R aim-assist (stretch)")
    ap.add_argument("--show", action="store_true", help="open an overlay window")
    ap.add_argument("--n", type=int, default=0, help="stop after N iterations (0 = forever)")
    ap.add_argument("--conf", type=float, help="override confidence threshold")
    ap.add_argument("--engine", help="override TensorRT engine path")
    args = ap.parse_args()

    if args.nudge:
        CFG.nudge = True
    if args.conf is not None:
        CFG.conf_thres = CFG.fire_conf = args.conf
    if args.engine:
        CFG.engine_path = args.engine

    from stim import StimClient
    stim = StimClient(CFG, dry_run=args.dry_run)
    source, source_grabs = build_source(args)

    # For the telemetry source we optionally grab our own frame for the overlay.
    grab_for_overlay = None
    if args.show and not source_grabs:
        import mss
        import numpy as np
        _sct = mss.mss()
        _mon = _sct.monitors[1]

        def grab_for_overlay():
            raw = np.asarray(_sct.grab(_mon))
            return np.ascontiguousarray(raw[:, :, :3])

    running = {"go": True}
    signal.signal(signal.SIGINT, lambda *_: running.__setitem__("go", False))

    print(f"cheat-loop: source={args.source} dry_run={args.dry_run} "
          f"nudge={CFG.nudge} -> stim {CFG.stim_host}:{CFG.stim_port}")
    print("Ctrl-C to stop.\n")

    loop_ms, fires, i = [], 0, 0
    try:
        while running["go"] and (args.n == 0 or i < args.n):
            t0 = time.perf_counter()

            img = grab_for_overlay() if grab_for_overlay else None
            frame = source.read(img=img)
            cmds = target_mod.decide(frame, CFG)
            fired = any(stim.send(c) for c in cmds)
            if fired:
                fires += 1

            dt = (time.perf_counter() - t0) * 1000.0
            loop_ms.append(dt)

            if args.show:
                import cv2
                import overlay
                tgt = target_mod.select(frame, CFG)
                annotated = overlay.draw(frame, target=tgt, firing=fired)
                if annotated is not None:
                    cv2.imshow("cheat-loop", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

            if i % 30 == 0 and loop_ms:
                fps = 1000.0 / statistics.mean(loop_ms[-30:])
                print(f"\r[{i:5d}] {len(frame.dets):2d} dets  "
                      f"{fps:4.1f} FPS  fires={fires} suppressed={stim.suppressed}",
                      end="", flush=True)
            i += 1
    finally:
        print()
        if loop_ms:
            print(f"iterations={i}  mean={statistics.mean(loop_ms):.1f}ms  "
                  f"median={statistics.median(loop_ms):.1f}ms  "
                  f"fires={fires}  suppressed={stim.suppressed}")
        stim.close()
        source.close()
        if args.show:
            try:
                import cv2
                cv2.destroyAllWindows()
            except Exception:
                pass


if __name__ == "__main__":
    main()
