# Kickoff prompt (paste into Claude Opus / Cursor)

Copy the block below to start a session. Attach or place the AUVON PDF at `docs/AUVON-AS8016-5languages-sms-V1.0-211014-80x130mm.pdf` before running.

---

## Prompt

You are the lead embedded engineer on this repo. Read **`CLAUDE.md`** and **`AGENTS.md`** fully before writing code.

**Project:** Neuromuscular aim-assist that drives an **AUVON AS8016** TENS/EMS unit through an **Axiometa Genesis Mini v1 rev 2** (ESP32-S3-Mini-1-N4R2) running **MicroPython**. External **MOSFET** circuits simulate five front-panel buttons; four **relays** independently switch outputs A1, A2, B1, B2. Nine GPIO lines total. Deliver a **Python API** so other software can control the hardware.

**TENS reference:** Use `docs/AUVON-AS8016-5languages-sms-V1.0-211014-80x130mm.pdf` (AS8016 manual) for button functions, channel layout, and safety context.

**Network:** Wi-Fi SSID and password are in `config/device_secrets.toml`. Target deployment from **VS Code on Windows** over **Wi-Fi** after initial USB flash.

**Authority:** You may restructure the repo, choose tools, and "boil the ocean" as long as you honor the spirit of `CLAUDE.md` — especially phased delivery and electrical safety.

**Start here (mandatory order):**

1. **Phase 0–1:** Help me set up MicroPython in VS Code, flash the Genesis Mini, connect to Wi-Fi, and get **wireless code sync** working (WebREPL / mpremote / extension — your call).
2. **Only after Wi-Fi deploy works:** GPIO bring-up for 9 pins and the Python control API.

Do not begin MOSFET/relay code until Phase 1 exit criteria in `CLAUDE.md` are met. At each step, give exact Windows commands, expected output, and how to verify success.

Begin with Phase 0.
