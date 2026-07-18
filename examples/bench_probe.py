# examples/bench_probe.py — multimeter bring-up helper (Phase 2)
#
# Holds a single GPIO line asserted (steady) so you can measure it, then
# releases it. Works for both relay lines (latched) and button lines (which
# are normally momentary — here we hold them for the meter).
#
# On the board REPL:
#   from lib.tens_controller import TensController
#   import bench_probe
#   bench_probe.attach(TensController())
#   bench_probe.on("A1")     # assert -> measure GPIO to GND (~0V active-low)
#   bench_probe.off("A1")    # release -> ~3.3V
#   bench_probe.pins()       # show the name -> GPIO map
#
# Raw-pin note: with no driver board attached you are measuring the ESP32 pin
# directly. Our code drives 0 to "assert" (active-low), so asserted reads ~0V
# and released reads ~3.3V. Driver-board polarity is a separate, later concern.

from config import pins as P

_t = None


def attach(controller=None):
    """Attach a controller (builds one if not given) and drive all lines safe."""
    global _t
    if controller is None:
        from lib.tens_controller import TensController
        controller = TensController()
    _t = controller
    _t.all_off()
    print("attached; all lines safe")


def _gpio(name):
    if name in P.RELAY_PINS:
        return P.RELAY_PINS[name]
    return P.BTN_PINS[name]


def _active_low(name):
    # Buttons and relays can have DIFFERENT polarity, so resolve per line.
    return P.RELAY_ACTIVE_LOW if name in P.RELAY_PINS else P.BTN_ACTIVE_LOW


def _volts(name, asserted):
    # asserted level = 0 if active-low else 1 -> 0V / 3.3V
    if asserted:
        return 0.0 if _active_low(name) else 3.3
    return 3.3 if _active_low(name) else 0.0


def on(name):
    if name in P.RELAY_PINS:
        _t.output_enable(name, True)
    elif name in P.BTN_PINS:
        _t._buttons[name].hold(True)
    else:
        print("unknown line %r; try pins()" % name); return
    print("ASSERT  %-8s GPIO%-2d -> expect ~%.1fV to GND" % (name, _gpio(name), _volts(name, True)))


def off(name):
    if name in P.RELAY_PINS:
        _t.output_enable(name, False)
    elif name in P.BTN_PINS:
        _t._buttons[name].hold(False)
    else:
        print("unknown line %r; try pins()" % name); return
    print("release %-8s GPIO%-2d -> expect ~%.1fV to GND" % (name, _gpio(name), _volts(name, False)))


def pins():
    print("RELAYS :", {n: P.RELAY_PINS[n] for n in P.RELAY_PINS})
    print("BUTTONS:", {n: P.BTN_PINS[n] for n in P.BTN_PINS})
