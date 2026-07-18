# lib/wifi_manager.py — station-mode Wi-Fi with reconnect (Phase 1)
#
# In simulation this is a no-op that reports a fake IP so the rest of the
# stack (HTTP server, status()) can run on a PC.

from lib.hal import IS_SIMULATION, sleep_ms, ticks_ms, ticks_diff


class WiFiManager:
    def __init__(self, ssid, password, hostname="axiometa-tens"):
        self._ssid = ssid
        self._password = password
        self._hostname = hostname
        self._wlan = None
        self._sim_ip = "127.0.0.1"
        if not IS_SIMULATION:
            import network
            try:
                network.hostname(hostname)
            except Exception:
                pass
            self._wlan = network.WLAN(network.STA_IF)

    def connect(self, timeout_ms=15000):
        """Bring up the station interface. Returns IP string or None."""
        if IS_SIMULATION:
            print("[SIM][wifi] pretend-connected to %r as %s" % (self._ssid, self._sim_ip))
            return self._sim_ip

        self._wlan.active(True)
        if not self._wlan.isconnected():
            print("[wifi] connecting to %r ..." % self._ssid)
            self._wlan.connect(self._ssid, self._password)
            start = ticks_ms()
            while not self._wlan.isconnected():
                if ticks_diff(ticks_ms(), start) > timeout_ms:
                    print("[wifi] TIMEOUT connecting to %r" % self._ssid)
                    return None
                sleep_ms(250)
        ip = self._wlan.ifconfig()[0]
        print("[wifi] connected: %s (host %s)" % (ip, self._hostname))
        return ip

    def isconnected(self):
        if IS_SIMULATION:
            return True
        return bool(self._wlan and self._wlan.isconnected())

    def ip(self):
        if IS_SIMULATION:
            return self._sim_ip
        if self._wlan and self._wlan.isconnected():
            return self._wlan.ifconfig()[0]
        return None

    def ensure(self):
        """Reconnect if the link dropped. Cheap to call from a supervisor loop."""
        if IS_SIMULATION:
            return True
        if not self.isconnected():
            print("[wifi] link down, reconnecting")
            return self.connect() is not None
        return True
