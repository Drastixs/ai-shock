"""The data contract between loop stages.

Everything downstream of DETECT speaks these three types and nothing else, so
the vision path and the telemetry path are fully interchangeable. See
`loop-design.md` §6.
"""

from collections import namedtuple

# One detected box, in ORIGINAL SCREEN PIXELS (top-left origin, y down).
# cls: 0 = enemy (body), 1 = head.  conf: 0..1 (telemetry synthesizes 1.0).
Detection = namedtuple("Detection", "cls x1 y1 x2 y2 conf")

# One frame's worth of detections plus the frame size. img is optional and only
# carried for the on-screen overlay (BGR ndarray) — logic never reads it.
Frame = namedtuple("Frame", "w h dets img")

# One thing to do to one stim channel.
StimCommand = namedtuple("StimCommand", "channel burst_ms")


def box_center(d):
    """(cx, cy) of a Detection in screen pixels."""
    return (d.x1 + d.x2) * 0.5, (d.y1 + d.y2) * 0.5


def box_covers(d, px, py):
    """True if point (px, py) is inside detection d's box."""
    return d.x1 <= px <= d.x2 and d.y1 <= py <= d.y2


def box_width(d):
    return d.x2 - d.x1
