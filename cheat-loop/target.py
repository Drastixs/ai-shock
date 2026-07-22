"""SELECT + DECIDE — the pure heart of the loop (loop-design.md §3, §4).

No I/O, no hardware, no capture. Takes a Frame + Config, returns which target to
engage and what stim commands to send. This is what test_target.py exercises with
synthetic frames.
"""

from math import hypot

from types_ import Detection, StimCommand, box_center, box_covers, box_width

HEAD = 1
ENEMY = 0


def select(frame, cfg):
    """Pick the target: the detection whose center is nearest the crosshair.

    Crosshair = screen center. Drops low-confidence and tiny boxes. Among boxes
    that *cover* the crosshair, prefer a head (the aim bonus) over a body.
    Returns a Detection or None.
    """
    cx, cy = frame.w * 0.5, frame.h * 0.5

    cands = [
        d for d in frame.dets
        if d.conf >= cfg.conf_thres and box_width(d) >= cfg.min_box_px
    ]
    if not cands:
        return None

    # Boxes actually under the crosshair — these are firing candidates.
    covering = [d for d in cands if box_covers(d, cx, cy)]
    if covering:
        # Prefer a head if one is under the crosshair, else nearest covering box.
        heads = [d for d in covering if d.cls == HEAD]
        pool = heads if heads else covering
        return min(pool, key=lambda d: _dist(d, cx, cy))

    # Nothing under the crosshair yet — the nearest box is the aim target (nudge).
    return min(cands, key=lambda d: _dist(d, cx, cy))


def decide(frame, cfg):
    """Return the StimCommands to send this frame (usually 0 or 1).

    - FIRE: crosshair inside the target box and conf high enough -> trigger.
    - NUDGE (stretch, cfg.nudge): if the target is off-center horizontally,
      pulse the L/R muscle toward it. Vertical is out of scope.
    """
    target = select(frame, cfg)
    if target is None:
        return []

    cx, cy = frame.w * 0.5, frame.h * 0.5
    cmds = []

    if box_covers(target, cx, cy) and target.conf >= cfg.fire_conf:
        cmds.append(StimCommand(cfg.trigger_channel, cfg.fire_burst_ms))
        return cmds  # firing takes priority; don't also nudge

    if cfg.nudge:
        tx, _ = box_center(target)
        dx = tx - cx
        if abs(dx) > cfg.nudge_deadzone_px:
            ch = cfg.right_channel if dx > 0 else cfg.left_channel
            cmds.append(StimCommand(ch, cfg.nudge_burst_ms))

    return cmds


def _dist(d, cx, cy):
    bx, by = box_center(d)
    return hypot(bx - cx, by - cy)
