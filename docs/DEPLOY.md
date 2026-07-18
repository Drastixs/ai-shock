# Phase 1b — Wireless deploy (edit on PC, sync over Wi-Fi)

Phase 1 **exit criterion**: change a `.py` file on your PC, push it to the board without a USB data path, and run it.

> **Reality check:** plain `mpremote` is **serial/USB only** — it does *not* talk to the board over TCP/IP. The wireless path on MicroPython is **WebREPL** (port 8266). This doc reflects the setup that was actually verified on the hardware.

## 1. Get the board onto Wi-Fi (via USB, once)

`boot.py` reads `config/device_secrets.toml` and, on boot, connects Wi-Fi and starts WebREPL. Push the project over USB once (see the README "Flash & deploy" quickstart), then open the REPL and soft-reset:

```bat
mpremote connect COM6 repl
```
Press **Ctrl-D** to soft-reset and watch for:

```
[wifi] connected: 172.31.112.85 (host axiometa-tens)
[boot] WebREPL started -> ws://172.31.112.85:8266/
[boot] ready. ip=172.31.112.85
```

**Record that IP** in `config/device_secrets.toml` under `[device] ip = "..."`. Exit the REPL with **Ctrl-]**.

### `device_secrets.toml` requirements (learned the hard way)

- `[webrepl] enabled = true` **and** a `password` of **4–9 characters** — WebREPL raises `ValueError` and won't start outside that range. `boot.py` now checks this and prints a clear message.
- Inline comments after quoted values are fine (`password = "tenshack"  # note`) — the config reader strips them.
- `[app] http_autostart` (see below).

## 2. Confirm WebREPL is reachable

From the PC (must be on the **same 2.4 GHz network** as the board):

```bat
powershell -Command "Test-NetConnection 172.31.112.85 -Port 8266"
```

`TcpTestSucceeded : True` = WebREPL is up. If `PingSucceeded` is True but the TCP test fails, WebREPL didn't start (check the boot log) or the network blocks client-to-client traffic (common on phone hotspots — see Troubleshooting).

## 3. Deploy a file over Wi-Fi with `webrepl_cli.py`

Get the tool once:

```bat
curl -O https://raw.githubusercontent.com/micropython/webrepl/master/webrepl_cli.py
```

Push a file to the board over Wi-Fi (no USB):

```bat
py webrepl_cli.py -p tenshack wireless_test.py 172.31.112.85:/wireless_test.py
```

`sent N bytes` = wireless sync works. Pull a file back with the arguments reversed (`172.31.112.85:/file.py file.py`).

To get an interactive REPL **and** file transfer over Wi-Fi in one place, use a **local** copy of the WebREPL browser client: download <https://github.com/micropython/webrepl> and open `webrepl.html` from disk (`file://`). The *hosted* client at `https://micropython.org/webrepl/` cannot connect because an HTTPS page is blocked from opening an insecure `ws://` socket.

## The `http_autostart` flag — why the board stays reachable

`main.py`'s HTTP server runs a **blocking** asyncio loop. While it runs, the serial REPL and WebREPL cannot be serviced, so `mpremote` file ops fail with `could not enter raw repl` and WebREPL sync is impossible.

So `[app] http_autostart` defaults to **false**: the board boots to a REPL with WebREPL live (development-friendly). Start the API when you want it:

```python
from main import run; run()     # blocks; Ctrl-C to stop
```

Set `http_autostart = true` for a standalone controller that serves on boot — but then manage code by resetting the board, since the running server blocks sync.

## Golden rules

- **One serial owner at a time.** Never leave an `mpremote ... repl` session open in one window while running `mpremote` commands in another — exit with **Ctrl-]** first. A held port causes `could not enter raw repl` / access-denied errors.
- The board's **COM port changes** with USB mode: `303a:1001` (bootloader) vs `303a:4001` (running). Re-check with `mpremote connect list`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `could not enter raw repl` | another REPL session holds the port, or a blocking server runs on the board | Ctrl-] the other session; `taskkill /IM mpremote.exe /F`; tap RESET; keep `http_autostart=false` |
| Port 8266 closed after boot | WebREPL didn't start | check boot log: bad password length (4–9), missing password, or `enabled=false` |
| Ping OK but TCP 8266 fails | client isolation on the AP | phone hotspots often block device-to-device; use a real 2.4 GHz router |
| PC can't reach board IP | PC and board on different networks | put both on the same 2.4 GHz SSID; check `ipconfig` subnet matches |
| Wi-Fi never connects | 5 GHz-only SSID | ESP32-S3 is 2.4 GHz only |
| `webrepl.start` raises `ValueError` | password not 4–9 chars | shorten it |

> **USB is fine for the initial push and debugging, but USB-only is not "done."** Success requires wireless sync (WebREPL) to work — which it now does.
