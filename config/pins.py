# config/pins.py — GPIO assignment for Axiometa Genesis Mini v1 rev 2
#
# WHY these pins: we use ONLY the AX22 port GPIO (P1..P4) so we never collide
# with the board's reserved functions (NeoPixel 21, user button 45, battery
# sense 8/34/46, I2C 10/11, SPI 12/13/14). See CLAUDE.md hardware table.
#
# Group A (5x MOSFET / opto driver): momentary front-panel button bypass.
# Group B (4x relay): latched output-jack routing (A1, A2, B1, B2).
#
# ACTIVE LEVEL: many opto/MOSFET driver boards and low-cost relay boards are
# ACTIVE-LOW (pull the input low to turn the channel ON). Set the flags below
# to match YOUR board. Wrong polarity is the #1 cause of "everything is on at
# boot". Verify with a multimeter before connecting the TENS unit.

# --- Group A: button-bypass MOSFET lines (momentary pulse) -----------------
BTN_PINS = {
    "MODE":     4,   # P1_IO0 -> AS8016 "M" button (cycle mode P01..P24)
    "TIMER":    18,  # P4_IO2 -> AS8016 "Time" button. MOVED off GPIO3, which is
                     #           an ESP32-S3 strapping pin (a boot pull-down on
                     #           it forces a JTAG-source strapping level).
    "CHANNEL":  2,   # P1_IO2 -> AS8016 center A/B button (select channel)
    "INT_UP":   7,   # P2_IO0 -> AS8016 "+" button (intensity up)
    "INT_DOWN": 6,   # P2_IO1 -> AS8016 "-" button (intensity down)
}
# NOTE: GPIO3 (P1_IO1) is now free. Avoid it for boot-pulled lines (strapping).

# --- Group B: output-routing relay lines (latched on/off) ------------------
RELAY_PINS = {
    "A1": 5,   # P2_IO2 -> output jack A1 (channel A)
    "A2": 9,   # P3_IO0 -> output jack A2 (channel A)
    "B1": 16,  # P3_IO1 -> output jack B1 (channel B)
    "B2": 15,  # P3_IO2 -> output jack B2 (channel B)
}

# --- Driver polarity -------------------------------------------------------
# True  (active-low)  => a logic LOW at the GPIO asserts (turns ON) the channel.
#                        Typical of opto-input boards and blue relay MODULES.
# False (active-high) => a logic HIGH (3.3V) asserts. Correct for a direct
#                        N-channel MOSFET (gate on GPIO) or NPN (base via R).
#
# Set these to match the driver hardware you actually wired, then VERIFY with a
# meter: assert a line and confirm the load turns ON.
#
# This build uses bare N-channel MOSFETs for the buttons -> active-high.
# SAFETY — safe-state hold is done in HARDWARE:
#   * Buttons: external 10k pull-down from each MOSFET gate to GND, so the
#     MOSFETs stay OFF during the power-on window (before firmware) and any
#     high-Z state.
#   * Relays: the module supplies its own input pull-up (low-level trigger),
#     holding relays OFF when the pins float.
# No ESP32 internal pull is configured — the physical resistors are the single
# source of truth.
BTN_ACTIVE_LOW = False    # gate HIGH = MOSFET conducts = button "pressed"
                          # (bare N-ch MOSFETs w/ external 10k gate pull-downs)
# 4-ch relay MODULE set to LOW-LEVEL TRIGGER: IN LOW energizes the relay
# (NO->COM closes = output enabled). Chosen for reliable switching from 3.3V
# logic and fail-safe-off at boot (module's internal pull-up holds inputs HIGH
# = relays OFF while the ESP32 pins float during power-up).
RELAY_ACTIVE_LOW = True

# --- Button press timing ---------------------------------------------------
DEFAULT_PULSE_MS = 250    # a firm, deliberate push-button press. Reliably
                          # registered by the AS8016 and safely below the
                          # ~500ms hold/auto-repeat threshold. Range that works:
                          # ~150-350ms. Too short -> missed taps; too long ->
                          # the device treats it as a held button.
MIN_PRESS_INTERVAL_MS = 60  # debounce guard between consecutive presses

# --- Reserved pins (documented so we never reuse them) ---------------------
RESERVED = {
    21: "NeoPixel RGB (status LED)",
    45: "User button (INPUT_PULLUP)",
    8:  "Battery sense", 34: "Battery status", 46: "Battery enable",
    10: "I2C SDA (STEMMA QT)", 11: "I2C SCL (STEMMA QT)",
    12: "SPI", 13: "SPI", 14: "SPI",
}

NEOPIXEL_PIN = 21  # on-board RGB, used sparingly for status


def all_output_pins():
    """Every GPIO this project drives, for conflict-checking / boot reset."""
    return list(BTN_PINS.values()) + list(RELAY_PINS.values())


def assert_no_conflicts():
    """Raise if any assigned pin collides with a reserved pin or is duplicated."""
    used = all_output_pins()
    dupes = set(p for p in used if used.count(p) > 1)
    if dupes:
        raise ValueError("Duplicate pin assignment: %s" % sorted(dupes))
    clash = set(used) & set(RESERVED.keys())
    if clash:
        raise ValueError("Assigned pin(s) collide with reserved: %s" % sorted(clash))
    return True
