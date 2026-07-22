"""STIM output — send fire commands to the Genesis Mini over UDP (loop-design.md §5).

The loop is the SECOND layer of the safety envelope; the ESP32 firmware is the
first and authoritative one. Here we clamp burst length and enforce a per-channel
cooldown so detection flicker can't machine-gun a relay (or a muscle).

Idle = no packets = firmware watchdog opens all relays = stim off. So there is no
keepalive: we only ever send in order to fire.
"""

import json
import socket
import time


class StimClient:
    def __init__(self, cfg, dry_run=False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.addr = (cfg.stim_host, cfg.stim_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_fire = {}  # channel -> monotonic seconds of last send
        self.sent = 0
        self.suppressed = 0

    def send(self, cmd):
        """Send one StimCommand, applying clamp + cooldown. Returns True if sent."""
        now = time.monotonic()
        last = self._last_fire.get(cmd.channel)  # None until this channel fires
        if last is not None and (now - last) * 1000.0 < self.cfg.cooldown_ms:
            self.suppressed += 1
            return False

        burst = max(1, min(cmd.burst_ms, self.cfg.max_burst_ms))
        payload = json.dumps({"ch": cmd.channel, "ms": burst}).encode()

        if not self.dry_run:
            self.sock.sendto(payload, self.addr)
        self._last_fire[cmd.channel] = now
        self.sent += 1
        return True

    def send_all(self, cmds):
        return [self.send(c) for c in cmds]

    def close(self):
        self.sock.close()
