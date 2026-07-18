"""TelemetrySource — the ML-free detection path (loop-design.md §2b).

Reads the patched game's ground-truth boxes off UDP and emits the same Frame the
vision path does, so everything downstream is identical. This is the fallback /
bring-up / no-model demo source.

Packet (one datagram per rendered frame, to 127.0.0.1:28786):
  {"ms": <totalmillis>, "w": <int>, "h": <int>,
   "boxes": [[class, x1, y1, x2, y2], ...]}   # class first, screen pixels

Raw classes 0-5 (colour variants) are remapped to the 2-class scheme on read:
  body 0/2/4 -> 0 enemy,  head 1/3/5 -> 1 head   (same remap as training).
"""

import json
import socket

from types_ import Detection, Frame

# raw hook class id -> 2-class id
_REMAP = {0: 0, 2: 0, 4: 0, 1: 1, 3: 1, 5: 1}


class TelemetrySource:
    def __init__(self, cfg, poll_timeout_s=0.25):
        self.cfg = cfg
        self.poll_timeout_s = poll_timeout_s
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((cfg.telemetry_host, cfg.telemetry_port))
        self._last_ms = None      # game clock of the newest packet seen
        self._last_frame = Frame(0, 0, [], None)

    def read(self, img=None):
        """Return the freshest Frame. Blocks up to poll_timeout_s for a packet
        (so the loop is paced by the game's telemetry rate, not busy-spinning),
        then drains any backlog and keeps only the newest datagram. If nothing
        arrives before the timeout, returns an empty Frame (fail-safe: no
        detections -> no fire). img (optional BGR) is attached for overlay.
        """
        newest = None
        # Block for the first packet so we pace to telemetry arrival.
        self.sock.settimeout(self.poll_timeout_s)
        try:
            newest, _ = self.sock.recvfrom(65535)
        except socket.timeout:
            return Frame(self._last_frame.w, self._last_frame.h, [], img)
        # Drain any backlog non-blocking; the last one wins.
        self.sock.setblocking(False)
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except BlockingIOError:
                break
            newest = data

        if newest is None:
            # No new packet this iteration -> nothing to act on.
            return Frame(self._last_frame.w, self._last_frame.h, [], img)

        try:
            pkt = json.loads(newest)
        except (ValueError, UnicodeDecodeError):
            return Frame(self._last_frame.w, self._last_frame.h, [], img)

        w, h = int(pkt.get("w", 0)), int(pkt.get("h", 0))
        dets = []
        for b in pkt.get("boxes", []):
            if len(b) < 5:
                continue
            cls, x1, y1, x2, y2 = b[0], b[1], b[2], b[3], b[4]
            cls = _REMAP.get(int(cls))
            if cls is None:
                continue
            dets.append(Detection(cls, float(x1), float(y1),
                                  float(x2), float(y2), 1.0))  # ground truth

        self._last_ms = pkt.get("ms")
        frame = Frame(w, h, dets, img)
        self._last_frame = frame
        return frame

    def close(self):
        self.sock.close()
