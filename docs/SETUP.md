# Phase 0 — Toolchain setup (VS Code + MicroPython on Windows)

Goal: a working Windows dev environment that can flash the Genesis Mini over USB and then deploy Python to it over Wi-Fi.

## 1. Install the base tools

1. **Python 3.9+** for Windows (from python.org). During install tick **"Add Python to PATH"**.
2. **VS Code** (code.visualstudio.com).
3. **USB-serial driver.** The ESP32-S3 on the Genesis Mini uses native USB-CDC, so Windows 10/11 usually enumerates it with no driver. If it shows as an unknown device, install the CP210x/CH34x driver for your board revision.

## 2. Create the project venv (once)

Use the **`py` launcher** on Windows — bare `python`/`python3` often resolve to the Microsoft Store alias, which cannot build a venv (fails at `ensurepip`, exit 103). `py` uses your real python.org install.

From the repo root in **PowerShell**:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope Process RemoteSigned
python -m pip install -r requirements.txt
```

Or in **cmd.exe**: `py -m venv .venv` then `.venv\Scripts\activate.bat` then `python -m pip install -r requirements.txt`.

Verify (inside the activated venv, `python` and `mpremote` point at the venv):

```powershell
python -m esptool version
mpremote --help
```

Both must resolve. `mpremote` is our single tool for serial REPL, file copy, and Wi-Fi (TCP) deploy. The venv applies only to the window you activated it in — re-activate in each new shell.

## 3. VS Code extensions

Install from the Extensions panel:

- **Python** (Microsoft) — editing, linting, venv selection.
- **MicroPython Studio** *or* **IoPython** — file sync + REPL panel for MicroPython boards. Either is fine; this repo does not depend on either because `tools\deploy.ps1` uses `mpremote` directly.

Select the interpreter: `Ctrl+Shift+P` -> *Python: Select Interpreter* -> the `.venv` you just made.

## 4. Firmware download

Download the **standard 4 MiB** build (QSPI PSRAM, not octal SPIRAM) for `ESP32_GENERIC_S3` from <https://micropython.org/download/ESP32_GENERIC_S3/> and drop the `.bin` into a `firmware\` folder at the repo root. `tools\flash.ps1` auto-selects the newest one.

## 5. Secrets

```powershell
Copy-Item config\device_secrets.example.toml config\device_secrets.toml
```

`device_secrets.toml` is gitignored — Wi-Fi SSID/password and the WebREPL password live only there.

## Exit criteria (Phase 0)

- `esptool.py version` and `mpremote --help` run inside the venv.
- Firmware `.bin` is in `firmware\`.
- `config\device_secrets.toml` exists and has the Wi-Fi credentials.

Next: **docs/FLASH.md**.
