# lib/safe_boot.py — hardware E-stop / boot default
#
# WHY standalone: this must work even if the high-level controller failed to
# import. It talks straight to the pins and drives every line to its
# DE-ASSERTED (safe) level: all buttons released, all output jacks OPEN.
# Called from boot.py and reused by TensController.all_off().

from lib.hal import Pin
from config import pins as P


def _released_level(active_low):
    return 1 if active_low else 0


def all_off():
    """De-assert every project GPIO. Idempotent; safe to call any time.

    High-Z safe-state hold is handled in hardware (external gate pull-downs +
    relay-module pull-up), so no internal pull is configured here.
    """
    btn_level = _released_level(P.BTN_ACTIVE_LOW)
    for name, gpio in P.BTN_PINS.items():
        Pin(gpio, Pin.OUT, value=btn_level)
    relay_level = _released_level(P.RELAY_ACTIVE_LOW)
    for name, gpio in P.RELAY_PINS.items():
        Pin(gpio, Pin.OUT, value=relay_level)
    # Boot-time self-report: resolved polarity + the safe levels just written.
    print("[safe] buttons active_%s (released=%dV-ish) | relays active_%s (off=%dV-ish)"
          % ("low" if P.BTN_ACTIVE_LOW else "high", 3 if btn_level else 0,
             "low" if P.RELAY_ACTIVE_LOW else "high", 3 if relay_level else 0))
    print("[safe] all outputs de-asserted (buttons released, relays open)")
    return True
