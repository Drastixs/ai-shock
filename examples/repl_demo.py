# examples/repl_demo.py — manual bring-up test (Phase 2/3)
#
# Run pieces of this by hand in the serial or WebREPL prompt to verify each
# line before trusting the HTTP API. Nothing here ramps intensity autonomously.
#
#   mpremote connect COMx run examples/repl_demo.py
#   (or paste line-by-line in the REPL)

import sys
sys.path.append("/lib")
from lib.tens_controller import TensController
from lib.hal import sleep_ms

tens = TensController()
tens.all_off()

print("Status at boot:", tens.status())

# --- Group B: relays (safe to test first; no intensity involved) -----------
for jack in ("A1", "A2", "B1", "B2"):
    print("enable", jack)
    tens.output_enable(jack, True)
    sleep_ms(400)
    tens.output_enable(jack, False)
    sleep_ms(200)

# --- Group A: button taps --------------------------------------------------
tens.set_channel("A")
tens.mode_next()
tens.timer_adjust()
tens.intensity_up(1)     # single, deliberate step
sleep_ms(300)
tens.intensity_down(1)

print("Status after demo:", tens.status())
tens.all_off()
print("Demo complete; all outputs off.")
