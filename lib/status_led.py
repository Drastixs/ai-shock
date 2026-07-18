# lib/status_led.py — sparing use of the on-board NeoPixel (GPIO 21)
#
# Colours are intentionally few and meaningful (CLAUDE.md: use the LED
# sparingly). No animation loops that would compete with uasyncio timing.

from lib.hal import IS_SIMULATION

# colour name -> (r, g, b)
OFF = (0, 0, 0)
BOOTING = (16, 8, 0)      # dim amber
WIFI_OK = (0, 20, 0)      # green
WIFI_FAIL = (24, 0, 0)    # red
ACTIVITY = (0, 0, 24)     # blue blip on a button/relay action
ERROR = (30, 0, 0)


class StatusLED:
    def __init__(self, pin=21):
        self._np = None
        if IS_SIMULATION:
            return
        try:
            import machine
            import neopixel
            self._np = neopixel.NeoPixel(machine.Pin(pin), 1)
        except Exception as e:  # noqa: BLE001 - never let the LED break boot
            print("[led] unavailable: %s" % e)

    def set(self, colour):
        if self._np is None:
            if IS_SIMULATION:
                print("[SIM][led] %s" % (colour,))
            return
        try:
            self._np[0] = colour
            self._np.write()
        except Exception:
            pass

    def blip(self, colour=ACTIVITY, base=OFF, ms=40):
        """Short flash then return to base colour (used on control actions)."""
        from lib.hal import sleep_ms
        self.set(colour)
        sleep_ms(ms)
        self.set(base)
