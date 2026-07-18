# boot.py — runs first on every reset (Phase 1)
#
# Responsibilities, in order:
#   1. Put every project GPIO into its SAFE state ASAP (buttons released,
#      relays open) — before Wi-Fi, before anything else can go wrong.
#   2. Bring up Wi-Fi station mode from config/device_secrets.toml.
#   3. Start WebREPL so VS Code / mpremote / the WebREPL client can sync files
#      over Wi-Fi without USB.
#
# main.py handles the application (control API / HTTP server). Keeping boot.py
# minimal means a crash in the app never leaves the board unreachable.

import sys
sys.path.append("/lib")

from lib import safe_boot        # noqa: E402  -- de-assert all outputs first
from lib.config_loader import load_secrets  # noqa: E402
from lib.status_led import StatusLED, BOOTING, WIFI_OK, WIFI_FAIL  # noqa: E402
from lib.wifi_manager import WiFiManager     # noqa: E402

led = StatusLED()
led.set(BOOTING)

# 1) Hardware safe state (idempotent; main.py re-uses the same driver objects).
safe_boot.all_off()

# 2) Wi-Fi
cfg = load_secrets()
wifi_cfg = cfg.get("wifi", {})
dev_cfg = cfg.get("device", {})
wifi = WiFiManager(
    wifi_cfg.get("ssid", ""),
    wifi_cfg.get("password", ""),
    dev_cfg.get("hostname", "axiometa-tens"),
)
ip = wifi.connect()
led.set(WIFI_OK if ip else WIFI_FAIL)

# 3) WebREPL (skipped in simulation / if disabled in config)
webrepl_cfg = cfg.get("webrepl", {})
if ip and webrepl_cfg.get("enabled", False):
    pw = webrepl_cfg.get("password")
    if not pw:
        print("[boot] WebREPL enabled but no [webrepl] password set — not starting.")
    elif not (4 <= len(str(pw)) <= 9):
        print("[boot] WebREPL password must be 4-9 chars (got %d) — not starting."
              % len(str(pw)))
    else:
        try:
            import webrepl
            webrepl.start(password=pw)
            print("[boot] WebREPL started -> ws://%s:8266/" % ip)
        except Exception as e:  # noqa: BLE001
            print("[boot] WebREPL failed: %r" % (e,))

# Expose objects for main.py / REPL convenience.
print("[boot] ready. ip=%s" % ip)
