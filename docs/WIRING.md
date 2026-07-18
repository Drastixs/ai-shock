# Wiring & electrical assumptions

> **Safety is non-negotiable (CLAUDE.md).** The ESP32 GPIO must never touch the
> TENS unit's high-voltage output circuits. Everything below assumes isolated
> driver boards between the ESP32 and the AS8016.

## Pin map (AX22 ports only — no reserved-pin conflicts)

| Signal | GPIO | Port | Group | Driver |
|--------|------|------|-------|--------|
| BTN_MODE | 4 | P1_IO0 | A | MOSFET/opto (momentary) |
| BTN_TIMER | 18 | P4_IO2 | A | MOSFET (moved off GPIO3, a strapping pin) |
| BTN_CHANNEL | 2 | P1_IO2 | A | MOSFET/opto |
| BTN_INT_UP | 7 | P2_IO0 | A | MOSFET/opto |
| BTN_INT_DOWN | 6 | P2_IO1 | A | MOSFET/opto |
| RELAY_A1 | 5 | P2_IO2 | B | relay |
| RELAY_A2 | 9 | P3_IO0 | B | relay |
| RELAY_B1 | 16 | P3_IO1 | B | relay |
| RELAY_B2 | 15 | P3_IO2 | B | relay |

Defined in `config/pins.py`. `assert_no_conflicts()` verifies none collide with the reserved pins (NeoPixel 21, user button 45, battery 8/34/46, I2C 10/11, SPI 12/13/14). P4 is left free for expansion.

## Group A — button bypass (5× N-channel MOSFET, active-high)

Each line is wired **in parallel with a front-panel button** on the AS8016: GPIO → gate, source → GND, drain across the button contacts. Asserting the line briefly (a `pulse_ms`, default 120 ms) turns the MOSFET on and shorts the button, so the AS8016 registers a press.

- Polarity is **active-high** (`BTN_ACTIVE_LOW = False`) — gate HIGH (3.3 V) = MOSFET conducts = pressed; released/safe = 0 V.
- **Gate pull-downs:** each gate needs a **~10 kΩ resistor to GND** so the MOSFET is off while the pin floats at power-up (the ~100–300 ms before firmware runs). The firmware also enables the ESP32 **internal** pull-down as backup, but that only applies *after* boot — it does not cover the power-on window. **Physical gate pull-downs are required before the AS8016 is connected to a person.**
- BTN_TIMER is on **GPIO18 (P4_IO2)**, deliberately not GPIO3 (a strapping pin that a boot pull-down would drive).

## Group B — output routing (4× relay MODULE, active-low / low-level trigger)

Each relay switches one output jack (A1, A2, B1, B2) via **NO→COM** (normally open), so software enables/disables each electrode pair independently.

- Using a 4-channel relay **module** with a High/Low-trigger jumper, set to **LOW trigger**: `RELAY_ACTIVE_LOW = True`, so IN LOW energizes the relay. Chosen for reliable switching from 3.3 V logic and because the module's internal pull-up holds inputs HIGH (relays **off**) while the ESP32 pins float at power-up — fail-safe by construction, no external resistor needed.
- Power the module `VCC` from **5 V** (coils need it); tie module `GND` to ESP32 `GND`; drive `IN1–IN4` from GPIO 5, 9, 16, 15. If the module has a `VCC/JD-VCC` jumper, split it and power `JD-VCC` separately to keep the coil side opto-isolated.
- Keep channel A and channel B wiring physically separated — the AS8016 keeps A and B **galvanically isolated**; preserve that. Don't share a relay common between channels.
- Verify: at boot every relay must be **open** (jack disabled).

## Boot & E-stop guarantee

`boot.py` calls `safe_boot.all_off()` before anything else, and `TensController` constructs every driver in its de-asserted state. A single `tens.all_off()` (or `POST /all_off`) releases all buttons and opens all relays. Confirm this with a multimeter on the driver outputs **before** connecting the TENS unit to a person.

## Bring-up order (do relays before intensity)

1. Power the ESP32 and driver boards **with the TENS unit disconnected**.
2. Run `examples/repl_demo.py` and watch driver LEDs / meter — confirm each line asserts only when commanded and returns to safe.
3. Connect the AS8016 button lines, retest taps at low stakes.
4. Connect output jacks last; verify each relay routes the intended jack.
