# CLAUDE.md — Axiometa TENS Aim-Assist Controller

> **Read this file first.** It is the project constitution. Follow the spirit and outcomes even when the exact steps or file layout differ from what is written here.

---

## Mission

Build a **software-controlled interface** between an **Axiometa Genesis Mini** (MicroPython on ESP32-S3) and an **AUVON AS8016** TENS/EMS unit. The ESP32 drives external **MOSFET** and **relay** circuits that **simulate front-panel button presses** and **switch individual output lines**, so a separate neuromuscular aim-assist system can operate the device without manual input.

You have permission to **boil the ocean**: refactor, choose libraries, add tooling, restructure the repo, or take reasonable engineering shortcuts **as long as you stay aligned with the mission, safety constraints, and phased delivery below**.

---

## Hardware

### Microcontroller board

| Field | Value |
|-------|-------|
| Board | Axiometa Genesis Mini **v1, rev 2** |
| Module | ESP32-S3-Mini-1-**N4R2** (4 MB flash, 2 MB QSPI PSRAM) |
| Connectivity | USB-C (HW CDC + JTAG), Wi-Fi, BLE |
| Framework target | **MicroPython** (not Arduino unless needed for a one-time flash step) |

**Reserved on-board pins (do not use for TENS control without explicit reason):**

| GPIO | Function |
|------|----------|
| 21 | NeoPixel RGB |
| 45 | User button (INPUT_PULLUP) |
| 8, 34, 46 | Battery sense / status / enable |
| 10, 11 | I2C (STEMMA QT) |
| 12, 13, 14 | SPI bus |

**Available AX22 port GPIO (12 pins — assign 9 for this project):**

| Port | IO0 | IO1 | IO2 |
|------|-----|-----|-----|
| P1 | 4 | 3 | 2 |
| P2 | 7 | 6 | 5 |
| P3 | 9 | 16 | 15 |
| P4 | 1 | 17 | 18 |

Official pin map: [arduino-esp32 `axiometa_genesis_mini` variant](https://github.com/espressif/arduino-esp32/tree/master/variants/axiometa_genesis_mini).

Firmware: [MicroPython ESP32_GENERIC_S3](https://micropython.org/download/ESP32_GENERIC_S3/) — standard 4 MiB build (QSPI PSRAM, not octal SPIRAM).

### TENS device

| Field | Value |
|-------|-------|
| Model | AUVON **AS8016** |
| Reference doc | `docs/AUVON-AS8016-5languages-sms-V1.0-211014-80x130mm.pdf` (see `docs/REFERENCES.md`) |
| Channels | A (A1∥A2) and B (B1∥B2), galvanically isolated |
| Modes | P01–P16 TENS, P17–P24 EMS |

---

## Electrical architecture (9 GPIO outputs)

### Group A — Button bypass (5× MOSFET, active-low or active-high per opto/MOSFET board)

Simulate momentary front-panel presses. Default to **short pulse** (50–200 ms) unless hold behavior is required.

| # | Function | Maps to AS8016 control |
|---|----------|------------------------|
| 1 | Mode switch | M button — cycle program/mode |
| 2 | Timer | Time button — adjust session timer |
| 3 | Channel select | A/B center button — select channel A or B |
| 4 | Intensity increase | + button |
| 5 | Intensity decrease | − button |

### Group B — Output routing (4× relay)

Independently enable/disable each output jack while others may remain energized. Typical use: route pulses to specific electrode pairs under software control.

| # | Function |
|---|----------|
| 6 | Output A1 enable/disable |
| 7 | Output A2 enable/disable |
| 8 | Output B1 enable/disable |
| 9 | Output B2 enable/disable |

**Pin assignment:** Propose a concrete GPIO→function map in code (`config/pins.py` or similar), document it, and keep MOSFET vs relay logic separate. Verify no conflict with reserved pins.

**Electrical safety (non-negotiable):**

- ESP32 GPIO must **not** connect directly to TENS high-voltage circuits. Use optocouplers/MOSFET drivers for button lines and rated relays for output switching.
- Maintain **galvanic isolation** between patient-side TENS outputs and the ESP32 ground where the manual requires it.
- Provide **E-stop / all-off** behavior: a single API call and boot default must de-assert all MOSFETs and open all relays.
- Never drive intensity to maximum programmatically without explicit caller intent and rate limits.

---

## Network & deployment

Wi-Fi credentials live in `config/device_secrets.toml` (copy from `config/device_secrets.example.toml`):

- SSID: `Short Phone`
- Password: *(see local secrets file — do not commit)*

**Goal:** Develop in **VS Code on Windows**, deploy Python to the board **over Wi-Fi** after an initial USB flash.

Preferred toolchain (choose best fit; document what you pick):

1. **Initial USB flash:** `esptool.py` + MicroPython `.bin` for ESP32-S3
2. **Wi-Fi deploy:** `mpremote connect <IP>`, WebREPL, MicroPython Studio, IoPython, or `micro-ota` / similar
3. **VS Code extensions:** MicroPython Studio and/or IoPython; Python 3.7+ with `mpremote` and `esptool` on PATH

If true **firmware OTA** is impractical, **Wi-Fi filesystem sync** (WebREPL / mpremote over TCP) still satisfies the requirement — say so explicitly and proceed.

---

## Phased delivery (strict order)

### Phase 0 — Toolchain & documentation *(do this first)*

- [ ] Confirm VS Code + Python venv with `esptool`, `mpremote`
- [ ] Install and document a MicroPython VS Code workflow for this user on **Windows**
- [ ] Place/read AUVON PDF in `docs/`; summarize controls in code comments or `docs/`
- [ ] Create minimal repo layout: `boot.py`, `main.py`, `lib/`, `config/`

### Phase 1 — MicroPython on board + Wi-Fi flashing

- [ ] Flash MicroPython via USB (BOOT + RESET procedure on Genesis Mini)
- [ ] Verify REPL over USB serial
- [ ] Connect to `Short Phone` Wi-Fi from `boot.py` or `main.py`
- [ ] Enable WebREPL or equivalent; verify **deploy/sync from VS Code over Wi-Fi**
- [ ] Document IP discovery, reconnect, and troubleshooting (COM port, driver, firewall)

**Exit criteria:** User can edit a `.py` file in VS Code, sync to the board without USB, and see `print()` output.

### Phase 2 — GPIO bring-up

- [ ] Assign and document 9 pins
- [ ] Implement low-level drivers: `ButtonBypass` (momentary pulse), `OutputRelay` (latched on/off)
- [ ] Test each line with serial REPL commands before building HTTP API
- [ ] Boot defaults: all outputs safe/off

### Phase 3 — Python control API

Provide a **clean Python API** (module import + optional network API) so other code/agents can control hardware without knowing GPIO numbers.

Minimum surface:

```python
# Illustrative — implement with typing, docstrings, and error handling
tens.set_channel("A")          # or "B"
tens.mode_next()
tens.timer_adjust()
tens.intensity_up(steps=1)
tens.intensity_down(steps=1)
tens.output_enable("A1", True)
tens.output_enable("A2", False)
tens.all_off()
tens.status()  # dict: channel, outputs, last action, wifi, uptime
```

Optional but valuable: **asyncio HTTP** or **WebSocket** on port 8080 for remote control from the aim-assist system. If added, include OpenAPI-style route list and example `curl` commands.

---

## Coding standards

- MicroPython-compatible Python (no heavy stdlib; prefer `uasyncio` where needed)
- Small modules under `lib/`; board entrypoint `main.py`
- Secrets only in `config/device_secrets.toml` — never hardcode in committed files
- Log meaningful events to serial; use NeoPixel (GPIO 21) sparingly for status (Wi-Fi connected, error, activity)
- Comment **why**, not **what**, for non-obvious timing/isolation choices

---

## Authority & scope

| You may | You must not |
|---------|--------------|
| Restructure repo, add deps, pick VS Code extensions | Skip Phase 0/1 to jump straight to GPIO |
| Change pin map with documented rationale | Connect ESP32 GPIO directly to TENS HV |
| Add tests, CLI, HTTP API, simulation mode | Commit Wi-Fi passwords to git |
| Stop and report if Wi-Fi deploy is impossible on this board | Assume Arduino toolchain unless MicroPython fails |

When blocked, produce a **short diagnostic report** (what you tried, error output, next best option) and continue with the closest workable path (e.g. USB `mpremote` fallback) without abandoning the Wi-Fi goal.

---

## Success definition

1. MicroPython runs on the Genesis Mini v1r2.
2. Code deploys from VS Code over Wi-Fi (or documented equivalent wireless sync).
3. Nine GPIO lines are mapped, tested, and wrapped in a documented Python API.
4. A developer can call that API to simulate all five button functions and control four output relays independently.
5. `docs/` explains wiring assumptions, pin map, flash/deploy steps, and API usage.

---

## Kickoff instruction for the agent

Start with: *"Phase 0 and Phase 1 — set up MicroPython in VS Code on Windows and get wireless deploy working on the Axiometa Genesis Mini before any TENS GPIO work."* Then proceed through phases in order.
