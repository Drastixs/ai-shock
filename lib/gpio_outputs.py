# lib/gpio_outputs.py — low-level output drivers (Phase 2)
#
# Two driver classes, kept deliberately separate because the electrical
# behaviour differs:
#   ButtonBypass -> momentary MOSFET/opto pulse that emulates a human tapping a
#                   front-panel button. Never held on unless explicitly asked.
#   OutputRelay  -> latched relay that routes a TENS output jack on/off.
#
# Both honour per-board active-low polarity from config/pins.py so that the
# DE-ASSERTED (safe) state is written at construction time. This guarantees the
# board boots with all buttons released and all output jacks OPEN.

from lib.hal import Pin, sleep_ms, ticks_ms, ticks_diff


class ButtonBypass:
    """One MOSFET/opto line that simulates a momentary button press."""

    def __init__(self, name, gpio, active_low=True, min_interval_ms=60):
        self.name = name
        self.gpio = gpio
        self._active_low = active_low
        self._min_interval_ms = min_interval_ms
        self._last_press = None
        # asserted = "button pressed", deasserted = "button released"
        self._asserted_level = 0 if active_low else 1
        self._released_level = 1 if active_low else 0
        # Construct already released (safe). Safe-state hold when the pin is
        # high-Z is handled in HARDWARE now: external 10k gate pull-downs on the
        # button MOSFETs, and the relay module's own input pull-up. No ESP32
        # internal pull is configured.
        self._pin = Pin(gpio, Pin.OUT, value=self._released_level)

    def _assert(self):
        self._pin.value(self._asserted_level)

    def _release(self):
        self._pin.value(self._released_level)

    def pulse_ms(self, duration=120):
        """Press then release after `duration` ms (a single tap).

        Rate-limited by min_interval_ms so a runaway caller cannot machine-gun
        the button faster than the AS8016 can register.
        """
        now = ticks_ms()
        if self._last_press is not None:
            gap = ticks_diff(now, self._last_press)
            if gap < self._min_interval_ms:
                sleep_ms(self._min_interval_ms - gap)
        self._assert()
        sleep_ms(duration)
        self._release()
        self._last_press = ticks_ms()
        return True

    def hold(self, on):
        """Explicit press-and-hold (True) / release (False).

        Use sparingly — most AS8016 actions are taps. Holding + can ramp
        intensity, so callers must be deliberate.
        """
        if on:
            self._assert()
        else:
            self._release()
        return on

    def release(self):
        self._release()

    def state(self):
        return "pressed" if self._pin.value() == self._asserted_level else "released"


class OutputRelay:
    """One relay that latches a TENS output jack enabled/disabled."""

    def __init__(self, name, gpio, active_low=True):
        self.name = name
        self.gpio = gpio
        self._active_low = active_low
        self._on_level = 0 if active_low else 1
        self._off_level = 1 if active_low else 0
        self._enabled = False
        # Construct OPEN (jack disabled) — safe default. The relay module holds
        # its own input safe (pull-up) when the pin is high-Z; no internal pull.
        self._pin = Pin(gpio, Pin.OUT, value=self._off_level)

    def set(self, enabled):
        self._pin.value(self._on_level if enabled else self._off_level)
        self._enabled = bool(enabled)
        return self._enabled

    def enable(self):
        return self.set(True)

    def disable(self):
        return self.set(False)

    def is_enabled(self):
        return self._enabled

    def state(self):
        return "enabled" if self._enabled else "disabled"
