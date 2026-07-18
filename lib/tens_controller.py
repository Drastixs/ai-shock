# lib/tens_controller.py — high-level control API (Phase 3)
#
# The ONLY module upstream software should need. It maps AS8016 front-panel
# controls + four output jacks onto the driver layer and keeps a SOFTWARE
# MIRROR of device state, because the AS8016 gives no digital feedback.
#
# State memory (per channel A/B): selected channel, intensity level (0-20),
# and program mode (P01-P24). This is what makes the REST getters
# (GET /channel, /intensity, /mode) and absolute setters (PUT ...) possible:
# a setter computes how many button presses move from the remembered current
# value to the target.
#
# IMPORTANT: these mirrors reflect what we have COMMANDED, not what the LCD
# shows. If the device is also touched by hand, call set_channel()/set_mode()/
# set_intensity() to a known value to resync. Device behaviours modelled:
#   * cycling mode (M) resets that channel's intensity to 0
#   * channel-select toggles A<->B (one press)
#
# Safety (CLAUDE.md): boot/shutdown = all off; relative intensity moves are
# rate/step bounded; all_off() opens every relay (E-stop) so no output flows
# regardless of the mirrored level.

from lib.hal import ticks_ms, platform_name
from lib.gpio_outputs import ButtonBypass, OutputRelay
from lib import safe_boot
from lib import modes
from config import pins as P

VALID_CHANNELS = ("A", "B")
VALID_OUTPUTS = ("A1", "A2", "B1", "B2")
MAX_LEVEL = modes.MAX_LEVEL      # 20 discrete intensity levels (0 = off)
MAX_STEPS_PER_CALL = 5           # guard for the RELATIVE intensity_up/down API
CHANNEL_OUTPUTS = {"A": ["A1", "A2"], "B": ["B1", "B2"]}


class TensController:
    def __init__(self, led=None, wifi=None, max_level=MAX_LEVEL):
        self._led = led
        self._wifi = wifi
        self._boot_ms = ticks_ms()
        self._max_level = max_level

        self._buttons = {
            name: ButtonBypass(name, gpio,
                               active_low=P.BTN_ACTIVE_LOW,
                               min_interval_ms=P.MIN_PRESS_INTERVAL_MS)
            for name, gpio in P.BTN_PINS.items()
        }
        self._relays = {
            name: OutputRelay(name, gpio, active_low=P.RELAY_ACTIVE_LOW)
            for name, gpio in P.RELAY_PINS.items()
        }

        # ---- software-mirrored device state --------------------------------
        # Assume the device powers on with channel A active (typical). Correct
        # it any time with set_channel(); the mirror follows commands.
        self._channel = "A"
        self._level = {"A": 0, "B": 0}       # 0..MAX_LEVEL
        self._mode_idx = {"A": 0, "B": 0}    # 0 => P01 ... 23 => P24
        self._last_action = "init"

    # ---- internal helpers -------------------------------------------------
    def _tap(self, btn_name):
        self._buttons[btn_name].pulse_ms(P.DEFAULT_PULSE_MS)
        if self._led:
            try:
                self._led.blip()
            except Exception:
                pass

    def _mark(self, action):
        self._last_action = action
        return action

    def _require_channel(self, channel):
        c = str(channel).upper()
        if c not in VALID_CHANNELS:
            raise ValueError("channel must be one of %s" % (VALID_CHANNELS,))
        return c

    # ======================================================================
    # CHANNEL  (resource: which group +/- and M affect)
    # ======================================================================
    def get_channel(self):
        return {"active": self._channel,
                "available": list(VALID_CHANNELS),
                "outputs": dict(CHANNEL_OUTPUTS)}

    def set_channel(self, channel):
        """Select channel 'A' or 'B'. State-aware: only presses the center
        button if we're not already on the target (it toggles A<->B)."""
        target = self._require_channel(channel)
        changed = self._channel != target
        if changed:
            self._tap("CHANNEL")
            self._channel = target
        self._mark("set_channel:%s" % target)
        return {"active": target, "changed": changed}

    # ======================================================================
    # INTENSITY  (0..MAX_LEVEL on the active channel)
    # ======================================================================
    def get_intensity(self):
        return {"level": self._level[self._channel], "max_level": self._max_level}

    def set_intensity(self, level):
        """Absolute set: fire +/- the exact number of steps to reach `level`."""
        level = int(level)
        if not (0 <= level <= self._max_level):
            raise ValueError("level must be an integer between 0 and %d"
                             % self._max_level)
        ch = self._channel
        delta = level - self._level[ch]
        steps = 0
        btn = "INT_UP" if delta > 0 else "INT_DOWN"
        for _ in range(abs(delta)):
            self._tap(btn)
            steps += 1
        self._level[ch] = level
        self._mark("set_intensity:%d(ch %s)" % (level, ch))
        return {"level": level, "steps_applied": steps}

    # Relative aliases (legacy / manual). Bounded per call for safety.
    def intensity_up(self, steps=1):
        return self._intensity_move("INT_UP", +1, steps, "intensity_up")

    def intensity_down(self, steps=1):
        return self._intensity_move("INT_DOWN", -1, steps, "intensity_down")

    def _intensity_move(self, btn, sign, steps, label):
        steps = int(steps)
        if steps < 1:
            return self._mark("%s:0" % label)
        if steps > MAX_STEPS_PER_CALL:
            raise ValueError("steps=%d exceeds MAX_STEPS_PER_CALL=%d"
                             % (steps, MAX_STEPS_PER_CALL))
        ch = self._channel
        applied = 0
        for _ in range(steps):
            projected = self._level[ch] + sign
            if projected < 0 or projected > self._max_level:
                break
            self._tap(btn)
            self._level[ch] = projected
            applied += 1
        return self._mark("%s:%d(ch %s)" % (label, applied, ch))

    # ======================================================================
    # MODE  (P01..P24 on the active channel)
    # ======================================================================
    def get_mode(self):
        return modes.describe(modes.mode_str(self._mode_idx[self._channel]))

    def modes_catalogue(self):
        return modes.catalogue()

    def set_mode(self, mode):
        """Absolute set: press M forward (it only cycles up) until the target
        program shows. Cycling resets this channel's intensity to 0 (device
        behaviour) -> intensity_reset."""
        idx = modes.mode_index(mode)   # validates, raises ValueError
        ch = self._channel
        presses = (idx - self._mode_idx[ch]) % modes.NUM_MODES
        for _ in range(presses):
            self._tap("MODE")
        self._mode_idx[ch] = idx
        reset = presses > 0
        if reset:
            self._level[ch] = 0
        m = modes.mode_str(idx)
        self._mark("set_mode:%s(ch %s)" % (m, ch))
        return {"mode": m, "master_mode": modes.master_mode(m),
                "intensity_reset": reset}

    def mode_next(self):
        """Relative alias: tap M once (advance one program, wraps P24->P01)."""
        self._tap("MODE")
        ch = self._channel
        self._mode_idx[ch] = (self._mode_idx[ch] + 1) % modes.NUM_MODES
        self._level[ch] = 0   # device resets intensity on mode change
        return self._mark("mode_next:%s(ch %s)"
                          % (modes.mode_str(self._mode_idx[ch]), ch))

    # ======================================================================
    # TIMER
    # ======================================================================
    def timer_adjust(self):
        """Tap Time: step the session timer (10-90 min on device)."""
        self._tap("TIMER")
        return self._mark("timer_adjust")

    # ======================================================================
    # OUTPUT ROUTING (relays)
    # ======================================================================
    def output_enable(self, jack, enabled):
        jack = str(jack).upper()
        if jack not in VALID_OUTPUTS:
            raise ValueError("output must be one of %s" % (VALID_OUTPUTS,))
        self._relays[jack].set(bool(enabled))
        return self._mark("output_%s:%s" % (jack, "on" if enabled else "off"))

    def outputs_for_channel(self, channel, enabled):
        c = self._require_channel(channel)
        for jack in CHANNEL_OUTPUTS[c]:
            self._relays[jack].set(bool(enabled))
        return self._mark("outputs_%s:%s" % (c, "on" if enabled else "off"))

    def get_outputs(self):
        return {name: r.is_enabled() for name, r in self._relays.items()}

    # ======================================================================
    # SAFETY
    # ======================================================================
    def all_off(self):
        """E-stop: release all buttons, open all relays. Mirrored level/mode
        persist (the device keeps them); opening relays cuts all output."""
        safe_boot.all_off()
        for r in self._relays.values():
            r.disable()
        for b in self._buttons.values():
            b.release()
        if self._led:
            try:
                from lib.status_led import OFF
                self._led.set(OFF)
            except Exception:
                pass
        return self._mark("all_off")

    # ======================================================================
    # INTROSPECTION
    # ======================================================================
    def status(self):
        return {
            "platform": platform_name(),
            "active_channel": self._channel,
            "channels": {
                c: {
                    "level": self._level[c],
                    "mode": modes.mode_str(self._mode_idx[c]),
                    "master_mode": modes.master_mode(modes.mode_str(self._mode_idx[c])),
                }
                for c in VALID_CHANNELS
            },
            "outputs": {name: r.state() for name, r in self._relays.items()},
            "buttons": {name: b.state() for name, b in self._buttons.items()},
            "last_action": self._last_action,
            "wifi_ip": self._wifi.ip() if self._wifi else None,
            "uptime_ms": ticks_ms() - self._boot_ms,
        }
