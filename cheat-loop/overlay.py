"""Overlay — draw what the loop sees, for the demo screen (loop-design.md §5/§8).

Boxes (green=enemy, cyan=head), the crosshair, the selected target (yellow), and
a red FIRE flash when the trigger goes. Pure drawing on a BGR ndarray; cv2 is
imported lazily so headless machines can still import the module.
"""

GREEN = (0, 255, 0)
CYAN = (255, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)


def draw(frame, target=None, firing=False):
    """Annotate frame.img in place and return it. Returns None if no image."""
    import cv2
    img = frame.img
    if img is None:
        return None

    cx, cy = frame.w // 2, frame.h // 2

    for d in frame.dets:
        colour = CYAN if d.cls == 1 else GREEN
        p1 = (int(round(d.x1)), int(round(d.y1)))
        p2 = (int(round(d.x2)), int(round(d.y2)))
        cv2.rectangle(img, p1, p2, colour, 2)
        cv2.putText(img, f"{'head' if d.cls == 1 else 'enemy'} {d.conf:.2f}",
                    (p1[0], max(p1[1] - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, colour, 1)

    if target is not None:
        p1 = (int(round(target.x1)), int(round(target.y1)))
        p2 = (int(round(target.x2)), int(round(target.y2)))
        cv2.rectangle(img, p1, p2, YELLOW, 3)

    # crosshair
    cv2.line(img, (cx - 12, cy), (cx + 12, cy), WHITE, 1)
    cv2.line(img, (cx, cy - 12), (cx, cy + 12), WHITE, 1)

    if firing:
        cv2.circle(img, (cx, cy), 26, RED, 3)
        cv2.putText(img, "FIRE", (cx + 34, cy + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, RED, 3)

    return img
