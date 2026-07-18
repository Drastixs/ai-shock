# Axiometa TENS Aim-Assist Controller

Software-controlled interface between an **Axiometa Genesis Mini** (ESP32-S3, MicroPython) and an **AUVON AS8016** TENS/EMS unit. The ESP32 drives external MOSFET and relay boards that simulate front-panel button presses and switch the four output jacks, exposing a clean Python + HTTP API so upstream software can operate the device without manual input.

See **`CLAUDE.md`** for the full project constitution and safety constraints.

## Status

| Phase | What | State |
|-------|------|-------|
| 0 | Toolchain, repo layout, pin map | ✅ code + docs done |
| 1 | Flash + Wi-Fi wireless deploy | ✅ tooling + docs done — **run on-device to verify** |
| 2 | 9-GPIO drivers (5 MOSFET, 4 relay) | ✅ code done, verified in simulation |
| 3 | Python + HTTP control API | ✅ code done, verified in simulation |

All firmware logic is verified under desktop CPython simulation. The remaining work is physical: flash the board, connect Wi-Fi, wire the driver boards, and run the on-device checks.

## Host setup (PC tools)

You need `esptool` + `mpremote` on your computer to flash and deploy. They're pinned in `requirements.txt`.

### Windows

On Windows, use the **`py` launcher** — the bare `python`/`python3` commands often resolve to the Microsoft Store alias, which cannot create a venv (fails at `ensurepip` with exit 103). `py` always uses your real python.org install.

```bat
py -m venv .venv
.venv\Scripts\activate.bat            :: cmd.exe  (PowerShell: .\.venv\Scripts\Activate.ps1)
python -m pip install -r requirements.txt
```

Once activated your prompt shows `(.venv)`, and plain `python` / `mpremote` point at the venv. Verify:

```bat
python -m esptool version
mpremote --help
```

Notes:
- The venv only applies to the window it's activated in. New shell → `cd` to the project → activate again. If plain `python` opens the Store, you forgot to activate.
- No venv? `py -m pip install --user -r requirements.txt` works too; then call tools as `py -m esptool ...` / `py -m mpremote ...`.
- To stop the alias hijacking `python`: Settings → Apps → Advanced app settings → App execution aliases → turn **off** `python.exe` and `python3.exe`.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Flash & deploy — Windows cmd quickstart

The full walkthrough (with troubleshooting) is in `docs/FLASH.md` + `docs/DEPLOY.md`. This is the condensed, copy-paste version we actually used. Run it from an activated venv (`(.venv)` in the prompt).

### 0. Firmware (once)

Download the **standard 4 MiB `ESP32_GENERIC_S3`** build (QSPI PSRAM — *not* the SPIRAM_OCT variant; this module is N4R2) from <https://micropython.org/download/ESP32_GENERIC_S3/> and put the `.bin` in a `firmware\` folder.

### 1. Find the board's COM port

```bat
mpremote connect list
```

The board is the `303a:xxxx` device (Espressif). **The COM number and PID change depending on mode:**
- `303a:1001` = ROM bootloader (download mode, for flashing)
- `303a:4001` = running MicroPython (for REPL + deploy)

So the port you flash on and the port you deploy on may differ (we saw COM5 → COM6). Re-run `mpremote connect list` after any reset. `mpremote connect auto` grabs the first board automatically.

### 2. Flash MicroPython (once)

Enter download mode: **hold BOOT, tap RESET, release BOOT.** Then (swap in your port + filename):

```bat
py -m esptool --chip esp32s3 --port COM5 erase-flash
py -m esptool --chip esp32s3 --port COM5 --baud 460800 write-flash 0 firmware\ESP32_GENERIC_S3-<version>.bin
```

Tap **RESET**. The board re-enumerates to a new COM port running MicroPython. Verify:

```bat
mpremote connect COM6 repl
```
```python
import sys; print(sys.implementation)     # -> micropython v1.28.0
```
Exit the REPL with **Ctrl+]** (leaving it open locks the port).

### 3. Push the project to the board

Fill in `config\device_secrets.toml` first (copy from the `.example`): set `[wifi]` SSID/password and a `[webrepl]` password of **4–9 characters** (WebREPL rejects anything longer). Then copy the code over USB (COM6 = your running-firmware port). Use recursive copy on a **fresh** board:

```bat
mpremote connect COM6 fs cp boot.py main.py :
mpremote connect COM6 fs cp -r lib config :
```

> **Gotcha:** `fs cp -r lib config :` only works cleanly when `:lib` / `:config` don't already exist — otherwise mpremote *nests* them (`:config/config/...`) and the board reads stale files. If in doubt, wipe first: `mpremote connect COM6 fs rm -r :lib :config`. Don't use `lib\*.py` — cmd doesn't expand the wildcard and mpremote doesn't glob.

### 4. Boot onto Wi-Fi and get the IP

```bat
mpremote connect COM6 repl
```

Press **Ctrl-D** (soft reset) and watch for `[wifi] connected: 172.31.x.x` and `[boot] WebREPL started -> ws://172.31.x.x:8266/`. Record the IP in `config\device_secrets.toml` under `[device] ip = "..."`. Exit with **Ctrl-]**.

### 5. Deploy over Wi-Fi (no USB) — via WebREPL

**Plain `mpremote` is USB/serial only — it does not work over IP.** The wireless path is **WebREPL** (port 8266). Confirm it's reachable, then push files with `webrepl_cli.py`:

```bat
powershell -Command "Test-NetConnection <ip> -Port 8266"          :: expect TcpTestSucceeded : True
curl -O https://raw.githubusercontent.com/micropython/webrepl/master/webrepl_cli.py
py webrepl_cli.py -p <webrepl-password> main.py <ip>:/main.py
```

Edit on PC → `py webrepl_cli.py -p <pw> <file> <ip>:/<file>` → reset. No cable. For an interactive REPL over Wi-Fi, open a **local** copy of `webrepl.html` (the hosted HTTPS client can't open `ws://`). Full detail + the `http_autostart` flag in `docs/DEPLOY.md`.

### Common gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Access is denied` / `port is in use` | a REPL or serial monitor still holds the port | exit REPL with **Ctrl-]**; `taskkill /IM mpremote.exe /F`; close VS Code serial / Arduino IDE / PuTTY |
| `could not enter raw repl` | another REPL session open, or a blocking server running on the board | Ctrl-] the other session; tap RESET; keep `[app] http_autostart = false` |
| `could not open COMx` after reset | board re-enumerated to a new port | re-run `mpremote connect list` (`1001`=bootloader, `4001`=running) |
| WebREPL port 8266 closed after boot | bad/missing `[webrepl]` password (must be 4–9 chars) | fix password; check the boot log |
| Ping OK but TCP 8266 fails | client isolation (common on phone hotspots) | use a real 2.4 GHz router; put PC + board on the same SSID |
| `Python was not found` / venv fails at `ensurepip` | Microsoft Store `python` alias | use `py` (see Host setup) |
| `The system cannot find the file specified` on flash | `<version>` left literal / wrong path | `dir firmware` and use the exact `.bin` name |

## Do this in order

1. **`docs/SETUP.md`** — install VS Code, Python venv, `esptool` + `mpremote`, firmware, secrets.
2. **`docs/FLASH.md`** — one-time USB flash of MicroPython (BOOT+RESET, `tools\flash.ps1`).
3. **`docs/DEPLOY.md`** — Wi-Fi deploy loop (`tools\deploy.ps1 -Target <ip>`). **Do not start GPIO until wireless deploy prints from the board.**
4. **`docs/WIRING.md`** — driver boards, isolation, pin map, bring-up order.
5. **`docs/API.md`** — Python module + HTTP API reference.

## Repo layout

```
requirements.txt        Host-side PC tools (esptool, mpremote)
boot.py                 Wi-Fi + WebREPL init; drives GPIO safe first
main.py                 App entry: builds controller, serves HTTP API
config/
  pins.py               GPIO map + polarity + conflict check
  device_secrets.toml   Wi-Fi/WebREPL creds (gitignored)
lib/
  hal.py                machine.Pin on-board / logging fake in simulation
  gpio_outputs.py       ButtonBypass (pulse) + OutputRelay (latched)
  tens_controller.py    High-level API (the surface upstream code uses)
  http_api.py           uasyncio HTTP server on :8080
  wifi_manager.py       Station-mode Wi-Fi + reconnect
  config_loader.py      Tiny TOML reader for secrets
  status_led.py         NeoPixel status (sparingly)
  safe_boot.py          E-stop / boot default: all outputs off
tools/
  flash.ps1             USB flash helper
  deploy.ps1            mpremote sync over USB or Wi-Fi
examples/
  repl_demo.py          Manual bring-up test
docs/                   SETUP / FLASH / DEPLOY / WIRING / API / REFERENCES
```

## Try it now (no hardware, desktop Python)

```bash
python3 -c "from lib.tens_controller import TensController; t=TensController(); t.set_channel('A'); t.intensity_up(2); print(t.status())"
```

Prints the full status dict with `"platform": "simulation (CPython)"` — the same code path that runs on the board.

## Safety

The ESP32 never connects directly to TENS high-voltage circuits — optoisolated drivers for buttons, rated relays for outputs. Boot default and `all_off()` de-assert everything. Intensity moves are bounded and never auto-ramp to max. Read `docs/WIRING.md` and the safety section of `CLAUDE.md` before connecting the AS8016 to a person.
