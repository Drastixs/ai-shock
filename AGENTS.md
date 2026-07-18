# AGENTS.md — Cursor agent operating instructions

This repo controls an **AUVON AS8016 TENS unit** via an **Axiometa Genesis Mini** running **MicroPython**. Read **`CLAUDE.md`** for full hardware, safety, and phase requirements.

---

## Your role

You are an embedded Python engineer helping the user:

1. Set up **VS Code + MicroPython** on **Windows**
2. Flash the board and enable **Wi-Fi-based code deployment**
3. Build a **9-GPIO control stack** (5× button-bypass MOSFET, 4× output relays)
4. Expose a **Python API** for upstream aim-assist software

You may diverge from specific file names or tools if a better approach still meets `CLAUDE.md` success criteria.

---

## Session startup checklist

1. Read `CLAUDE.md` end-to-end
2. Check for `docs/AUVON-AS8016-5languages-sms-V1.0-211014-80x130mm.pdf`; if missing, tell the user to add it and use `docs/REFERENCES.md` mirrors meanwhile
3. Check `config/device_secrets.toml` exists (copy from `config/device_secrets.example.toml` if not)
4. Identify current phase from git/files present; **do not start GPIO until Wi-Fi deploy works**

---

## Phase gate rules

| Phase | Entry | Exit before next phase |
|-------|-------|------------------------|
| **0** Toolchain | Empty or fresh repo | VS Code workflow documented; Python tools installed |
| **1** Wi-Fi deploy | Phase 0 done | `mpremote`/WebREPL over Wi-Fi syncs `main.py` successfully |
| **2** GPIO | Phase 1 done | All 9 lines toggle from REPL; safe defaults on boot |
| **3** API | Phase 2 done | Importable `lib/tens_controller.py` (or equivalent) + usage example |

If the user asks to skip ahead, warn once, then do the minimum Phase 1 verification (Wi-Fi REPL) before GPIO.

---

## Recommended repo layout (create as needed)

```
axiometa_anthropic_hack/
├── CLAUDE.md
├── AGENTS.md
├── boot.py                 # Wi-Fi + WebREPL init
├── main.py                 # Entry: start API / supervisor
├── config/
│   ├── device_secrets.toml # gitignored
│   ├── device_secrets.example.toml
│   └── pins.py             # GPIO assignment
├── lib/
│   ├── tens_controller.py  # High-level API
│   ├── gpio_outputs.py     # MOSFET + relay drivers
│   └── wifi_manager.py
├── docs/
│   ├── REFERENCES.md
│   └── AUVON-*.pdf
└── tools/
    ├── flash.ps1           # esptool helpers for Windows
    └── deploy.ps1          # mpremote sync over IP
```

---

## Windows commands (prefer these)

```powershell
# One-time venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install esptool mpremote

# Flash MicroPython (USB — replace COM port)
esptool.py --chip esp32s3 --port COMx erase_flash
esptool.py --chip esp32s3 --port COMx --baud 460800 write_flash 0 ESP32_GENERIC_S3-*.bin

# Serial REPL
mpremote connect COMx repl

# Wi-Fi deploy (after WebREPL / mpremote TCP enabled)
mpremote connect 192.168.x.x fs cp main.py :main.py
mpremote connect 192.168.x.x repl
```

Document the board's **BOOT + RESET** sequence for download mode in `docs/FLASH.md` when created.

---

## GPIO planning (Genesis Mini v1r2)

Use **AX22 port pins only** for the 9 outputs. Suggested starting map (adjust in `config/pins.py` with user confirmation):

| Signal | GPIO | Port |
|--------|------|------|
| BTN_MODE | 4 | P1_IO0 |
| BTN_TIMER | 3 | P1_IO1 |
| BTN_CHANNEL | 2 | P1_IO2 |
| BTN_INT_UP | 7 | P2_IO0 |
| BTN_INT_DOWN | 6 | P2_IO1 |
| RELAY_A1 | 5 | P2_IO2 |
| RELAY_A2 | 9 | P3_IO0 |
| RELAY_B1 | 16 | P3_IO1 |
| RELAY_B2 | 15 | P3_IO2 |

Leave P4 and on-board special pins unassigned unless more IO is needed.

**Driver behavior:**

- MOSFET lines: `pulse_ms(duration=100)` — emulate human button press
- Relay lines: `set(enabled: bool)` — latched routing
- `all_off()` on boot and on API shutdown

---

## API design notes

- High-level module should not expose raw GPIO numbers to callers
- Include `status()` returning channel selection state (if tracked), relay states, Wi-Fi IP, uptime
- If HTTP server added: bind `0.0.0.0`, port 8080, JSON request/response, no auth in dev (note in docs — add token later)
- Provide `examples/repl_demo.py` or REPL one-liners for manual test

---

## Safety reminders (repeat when wiring)

- Optoisolated MOSFET drivers for front-panel buttons; separate relay board for output jacks
- Default all outputs **inactive** at boot
- Intensity changes should be bounded (`steps` parameter); never auto-ramp to max
- This is a **medical-adjacent** device — prefer explicit user actions over autonomous stimulation patterns unless the user requests otherwise

---

## When stuck

Produce:

1. Exact command run
2. Full error text
3. Likely cause (driver, COM port, firewall, WebREPL disabled, wrong firmware)
4. Next action

Offer USB serial fallback temporarily while fixing Wi-Fi deploy — do not treat USB-only as final success.

---

## Communication style

- Be concise and procedural during setup
- After each phase, summarize what works and the single next step
- Do not commit `device_secrets.toml` or ask the user to paste passwords into tracked files
