# main.py — application entrypoint (runs after boot.py) (Phase 3)
#
# boot.py has already: put GPIO safe, joined Wi-Fi, started WebREPL.
#
# IMPORTANT — why this does NOT auto-start a blocking server by default:
# the HTTP server runs a blocking asyncio loop. While it runs, the serial
# REPL and WebREPL cannot be serviced, so `mpremote` file ops fail with
# "could not enter raw repl" and WebREPL sync is impossible. During
# development we want the board reachable, so `http_autostart` defaults to
# False: boot leaves you at a REPL with WebREPL live, and you start the
# server explicitly when you want it.
#
#   Set [app] http_autostart = true in config/device_secrets.toml to make the
#   device serve the HTTP API automatically on boot (standalone controller).
#
# From the REPL you can always drive the hardware directly:
#     from main import tens
#     tens.set_channel("A"); tens.intensity_up(2)
# ...or start the network API by hand:
#     from main import run; run()

import sys
sys.path.append("/lib")

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from lib.config_loader import load_secrets
from lib.status_led import StatusLED
from lib.wifi_manager import WiFiManager
from lib.tens_controller import TensController
from lib.http_api import HttpApi

_cfg = load_secrets()
_wifi_cfg = _cfg.get("wifi", {})
_dev_cfg = _cfg.get("device", {})
_app_cfg = _cfg.get("app", {})

led = StatusLED()
wifi = WiFiManager(_wifi_cfg.get("ssid", ""), _wifi_cfg.get("password", ""),
                   _dev_cfg.get("hostname", "axiometa-tens"))

# Reuse an existing link if boot.py already connected; otherwise connect now.
if not wifi.isconnected():
    wifi.connect()

# The object upstream code / REPL drives:
tens = TensController(led=led, wifi=wifi)
tens.all_off()  # explicit safe state at app start

api = HttpApi(tens)


async def _supervisor():
    """Keep Wi-Fi up; cheap heartbeat."""
    while True:
        wifi.ensure()
        await asyncio.sleep(10)


async def _amain():
    await asyncio.gather(api.serve(), _supervisor())


def run():
    """Start the HTTP API + supervisor. Blocks (Ctrl-C to stop)."""
    print("[main] starting HTTP API + supervisor on :8080")
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        print("[main] interrupted; all_off()")
        tens.all_off()


# Auto-start ONLY if explicitly enabled in config. Default = stay at REPL so
# the board remains reachable over serial + WebREPL for development.
if __name__ == "__main__":
    if _app_cfg.get("http_autostart", False):
        run()
    else:
        print("[main] ready. http_autostart=off -> REPL + WebREPL available.")
        print("[main] call run() to serve the HTTP API, or drive tens.* directly.")
