"""Unit tests for the pure SELECT/DECIDE logic — no hardware, no capture.

Run:  python3 test_target.py
"""

from config import Config
from types_ import Detection, Frame
import target

W, H = 1024, 768
CX, CY = W // 2, H // 2  # crosshair = screen center (512, 384)


def frame(*dets):
    return Frame(W, H, list(dets), None)


def box_at(cx, cy, w=60, h=120, cls=0, conf=0.9):
    return Detection(cls, cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2, conf)


def run(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    return cond


def main():
    cfg = Config()
    ok = True

    # Enemy centered under the crosshair -> FIRE on the trigger channel.
    f = frame(box_at(CX, CY))
    cmds = target.decide(f, cfg)
    ok &= run("centered enemy -> fires trigger",
              len(cmds) == 1 and cmds[0].channel == cfg.trigger_channel)

    # Enemy far to the side, crosshair not covering -> no fire (nudge off).
    f = frame(box_at(CX + 300, CY))
    ok &= run("off-center enemy, nudge off -> no fire",
              target.decide(f, cfg) == [])

    # Same, with nudge ON -> pulses the RIGHT channel (enemy is to the right).
    cfg_n = Config(nudge=True)
    f = frame(box_at(CX + 300, CY))
    cmds = target.decide(f, cfg_n)
    ok &= run("off-center right, nudge on -> right channel",
              len(cmds) == 1 and cmds[0].channel == cfg_n.right_channel)

    # Enemy to the left with nudge -> LEFT channel.
    f = frame(box_at(CX - 300, CY))
    cmds = target.decide(f, cfg_n)
    ok &= run("off-center left, nudge on -> left channel",
              len(cmds) == 1 and cmds[0].channel == cfg_n.left_channel)

    # Low-confidence box under crosshair -> no fire.
    f = frame(box_at(CX, CY, conf=0.20))
    ok &= run("low-confidence -> no fire", target.decide(f, cfg) == [])

    # Head + body both cover crosshair -> select() prefers the head.
    f = frame(box_at(CX, CY, cls=0), box_at(CX, CY, w=30, h=30, cls=1))
    ok &= run("head preferred when both cover", target.select(f, cfg).cls == 1)

    # Two enemies cover the crosshair -> nearest-center wins.
    near = box_at(CX + 10, CY)
    far = box_at(CX - 25, CY)
    f = frame(far, near)
    ok &= run("nearest-to-crosshair wins", target.select(f, cfg) is near)

    # Tiny box (below min width) -> ignored.
    f = frame(box_at(CX, CY, w=4, h=4))
    ok &= run("tiny box ignored", target.decide(f, cfg) == [])

    # No detections -> no target, no fire.
    ok &= run("empty frame -> no fire", target.decide(frame(), cfg) == [])

    print("\nALL PASS" if ok else "\nFAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
