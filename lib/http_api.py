# lib/http_api.py — HTTP control surface (Phase 3)
#
# Canonical API is the REST scheme under /api/v1 (matches the team's
# AUVON-AS8016-API.html contract): GET reads mirrored state, PUT sets an
# absolute target, POST fires an action. JSON request + response bodies.
#
# The original flat routes (POST /intensity/up, /channel?ch=, ...) are kept as
# ALIASES so nothing already wired breaks.
#
# Binds 0.0.0.0:8080. Dev build has NO auth (see docs/API.md TODO). Runs on
# MicroPython uasyncio and CPython asyncio alike.

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

API = "/api/v1"


def _parse_qs(query):
    params = {}
    if not query:
        return params
    for pair in query.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
        elif pair:
            params[pair] = ""
    return params


def _truthy(v):
    return str(v).lower() in ("1", "true", "yes", "on")


# field hint per REST resource, for 400 error bodies
_FIELD = {API + "/intensity": "level", API + "/mode": "mode",
          API + "/channel": "active", API + "/outputs": "jack"}

ROUTES = [
    "GET  " + API + "/channel", "PUT " + API + "/channel",
    "GET  " + API + "/intensity", "PUT " + API + "/intensity",
    "GET  " + API + "/modes", "GET " + API + "/mode", "PUT " + API + "/mode",
    "GET  " + API + "/outputs", "PUT " + API + "/outputs",
    "POST " + API + "/timer", "POST " + API + "/all_off",
    "GET  " + API + "/status",
    "-- aliases --",
    "GET /status", "POST /mode/next", "POST /timer/adjust",
    "POST /channel?ch=A|B", "POST /intensity/up?steps=N",
    "POST /intensity/down?steps=N",
    "POST /output?jack=A1|A2|B1|B2&enabled=true|false", "POST /all_off",
]


class HttpApi:
    def __init__(self, controller, host="0.0.0.0", port=8080):
        self._c = controller
        self._host = host
        self._port = port

    # ---- routing ----------------------------------------------------------
    def _dispatch(self, method, path, params, body):
        c = self._c

        # ---------- canonical REST /api/v1 ----------
        if path == API + "/channel":
            if method == "GET":
                return 200, c.get_channel()
            if method == "PUT":
                return 200, c.set_channel(_field(body, "active"))
        elif path == API + "/intensity":
            if method == "GET":
                return 200, c.get_intensity()
            if method == "PUT":
                return 200, c.set_intensity(_field(body, "level"))
        elif path == API + "/modes":
            if method == "GET":
                return 200, c.modes_catalogue()
        elif path == API + "/mode":
            if method == "GET":
                return 200, c.get_mode()
            if method == "PUT":
                return 200, c.set_mode(_field(body, "mode"))
        elif path == API + "/outputs":
            if method == "GET":
                return 200, c.get_outputs()
            if method == "PUT":
                enabled = _truthy(body.get("enabled"))
                if body.get("channel"):
                    return 200, {"action": c.outputs_for_channel(body["channel"], enabled)}
                return 200, {"action": c.output_enable(_field(body, "jack"), enabled)}
        elif path == API + "/timer":
            if method == "POST":
                return 200, {"action": c.timer_adjust()}
        elif path == API + "/all_off":
            if method == "POST":
                return 200, {"action": c.all_off()}
        elif path == API + "/status":
            if method == "GET":
                return 200, c.status()

        # ---------- flat aliases (legacy) ----------
        elif path == "/" and method == "GET":
            return 200, {"service": "axiometa-tens", "api": API, "routes": ROUTES}
        elif path == "/status" and method == "GET":
            return 200, c.status()
        elif path == "/mode/next":
            return 200, {"ok": True, "action": c.mode_next()}
        elif path == "/timer/adjust":
            return 200, {"ok": True, "action": c.timer_adjust()}
        elif path == "/channel":
            return 200, {"ok": True, "result": c.set_channel(params.get("ch", ""))}
        elif path == "/intensity/up":
            return 200, {"ok": True, "action": c.intensity_up(int(params.get("steps", 1)))}
        elif path == "/intensity/down":
            return 200, {"ok": True, "action": c.intensity_down(int(params.get("steps", 1)))}
        elif path == "/output":
            jack = params.get("jack", "")
            return 200, {"ok": True, "action": c.output_enable(jack, _truthy(params.get("enabled", "false")))}
        elif path == "/all_off":
            return 200, {"ok": True, "action": c.all_off()}
        else:
            return 404, {"error": "not_found", "path": path, "routes": ROUTES}

        # path matched but method didn't
        return 405, {"error": "method_not_allowed", "path": path, "method": method}

    # ---- HTTP plumbing ----------------------------------------------------
    async def _handle(self, reader, writer):
        try:
            line = await reader.readline()
            if not line:
                await self._close(writer)
                return
            try:
                method, target, _ = line.decode().split(" ", 2)
            except ValueError:
                await self._respond(writer, 400, {"error": "bad_request"})
                return
            # read headers, capture content-length
            clen = 0
            while True:
                h = await reader.readline()
                if h in (b"\r\n", b"", b"\n") or h is None:
                    break
                try:
                    hn, _, hv = h.decode().partition(":")
                    if hn.strip().lower() == "content-length":
                        clen = int(hv.strip())
                except Exception:
                    pass
            body = {}
            if clen > 0:
                raw = await reader.readexactly(clen)
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {}
            path, _, query = target.partition("?")
            params = _parse_qs(query)
            try:
                code, obj = self._dispatch(method.upper(), path, params, body)
            except KeyError as e:
                code, obj = 400, {"error": "missing_field",
                                  "field": str(e).strip("'\""),
                                  "message": "required field %s missing" % e}
            except ValueError as e:
                code, obj = 400, {"error": "invalid_value",
                                  "field": _FIELD.get(path),
                                  "message": str(e)}
            except Exception as e:  # noqa: BLE001
                code, obj = 500, {"error": "internal", "message": str(e)}
            await self._respond(writer, code, obj)
        except Exception as e:  # noqa: BLE001
            print("[http] handler error: %s" % e)
            await self._close(writer)

    async def _respond(self, writer, code, obj):
        payload = json.dumps(obj)
        reason = {200: "OK", 400: "Bad Request", 404: "Not Found",
                  405: "Method Not Allowed", 409: "Conflict",
                  500: "Internal Server Error", 503: "Service Unavailable"}.get(code, "OK")
        resp = (
            "HTTP/1.1 %d %s\r\n"
            "Content-Type: application/json\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n"
            "Content-Length: %d\r\n\r\n%s"
        ) % (code, reason, len(payload), payload)
        writer.write(resp.encode() if hasattr(resp, "encode") else resp)
        await writer.drain()
        await self._close(writer)

    async def _close(self, writer):
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def serve(self):
        print("[http] listening on %s:%d (API %s)" % (self._host, self._port, API))
        server = await asyncio.start_server(self._handle, self._host, self._port)
        if server is not None and hasattr(server, "serve_forever"):
            async with server:
                await server.serve_forever()
        else:
            while True:
                await asyncio.sleep(3600)


def _field(body, name):
    """Pull a required field from a JSON body dict, else KeyError -> 400."""
    if not isinstance(body, dict) or name not in body:
        raise KeyError(name)
    return body[name]
