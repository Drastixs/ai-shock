# Phase 3 — Control API (unified)

Two equivalent ways to drive the hardware: import the Python module, or call the HTTP server. Neither exposes raw GPIO numbers. The HTTP surface implements the team's REST contract in `docs/AUVON-AS8016-API.html`; this doc is the source of truth for both.

## State model (important)

The AS8016 gives **no digital feedback**, so the controller keeps a **software mirror** of device state, per channel:

- `active channel` — A or B (assumed A at power-on; corrected by `set_channel`)
- `level` per channel — 0–20 (the device's 20 intensity steps; 0 = off)
- `mode` per channel — P01–P24 (P01–P16 TENS, P17–P24 EMS)

Getters return what we've **commanded**, not an LCD reading. If the unit is also touched by hand, re-issue a setter to a known value to resync. Two device behaviours are modelled: cycling mode (M) resets that channel's intensity to 0, and channel-select toggles A↔B with one press.

## Python module API

```python
from lib.tens_controller import TensController
tens = TensController()             # boots with all outputs OFF/open

# Channel
tens.get_channel()                  # {"active","available","outputs"}
tens.set_channel("B")               # state-aware -> {"active","changed"}

# Intensity (0-20 on the active channel)
tens.get_intensity()                # {"level","max_level":20}
tens.set_intensity(12)              # absolute -> {"level","steps_applied"}
tens.intensity_up(steps=2)          # relative alias (bounded per call)
tens.intensity_down(steps=1)

# Mode (P01-P24 on the active channel)
tens.get_mode()                     # {"mode","master_mode","feel"}
tens.set_mode("P18")                # absolute -> {"mode","master_mode","intensity_reset"}
tens.modes_catalogue()              # {"count":24,"modes":[...]}
tens.mode_next()                    # relative alias (tap M once)

# Outputs (relays) + device
tens.output_enable("A1", True)
tens.outputs_for_channel("B", True) # both jacks of a channel
tens.get_outputs()                  # {"A1":False,...}
tens.timer_adjust()
tens.all_off()                      # E-stop: open all relays
tens.status()                       # full mirrored snapshot
```

## HTTP API (canonical: REST under `/api/v1`)

Server: `main.run()` serves `0.0.0.0:8080`. Base URL `http://<device-ip>:8080/api/v1`. JSON in/out.

| Method | Path | Body / params | Returns |
|--------|------|---------------|---------|
| GET | `/api/v1/channel` | — | `{active, available, outputs}` |
| PUT | `/api/v1/channel` | `{"active":"A\|B"}` | `{active, changed}` |
| GET | `/api/v1/intensity` | — | `{level, max_level}` |
| PUT | `/api/v1/intensity` | `{"level":0-20}` | `{level, steps_applied}` |
| GET | `/api/v1/modes` | — | `{count, modes[]}` |
| GET | `/api/v1/mode` | — | `{mode, master_mode, feel}` |
| PUT | `/api/v1/mode` | `{"mode":"P01-P24"}` | `{mode, master_mode, intensity_reset}` |
| GET | `/api/v1/outputs` | — | `{A1,A2,B1,B2: bool}` |
| PUT | `/api/v1/outputs` | `{"jack":"A1","enabled":true}` or `{"channel":"A","enabled":true}` | `{action}` |
| POST | `/api/v1/timer` | — | `{action}` |
| POST | `/api/v1/all_off` | — | `{action}` (E-stop) |
| GET | `/api/v1/status` | — | full snapshot |

### Legacy flat aliases (kept working)

`GET /` · `GET /status` · `POST /mode/next` · `POST /timer/adjust` · `POST /channel?ch=A` · `POST /intensity/up?steps=N` · `POST /intensity/down?steps=N` · `POST /output?jack=A1&enabled=true` · `POST /all_off`

### Example calls

```bash
curl http://192.168.1.42:8080/api/v1/status
curl -X PUT http://192.168.1.42:8080/api/v1/channel   -H 'Content-Type: application/json' -d '{"active":"B"}'
curl -X PUT http://192.168.1.42:8080/api/v1/mode      -H 'Content-Type: application/json' -d '{"mode":"P18"}'
curl -X PUT http://192.168.1.42:8080/api/v1/intensity -H 'Content-Type: application/json' -d '{"level":12}'
curl -X PUT http://192.168.1.42:8080/api/v1/outputs   -H 'Content-Type: application/json' -d '{"jack":"A1","enabled":true}'
curl -X POST http://192.168.1.42:8080/api/v1/all_off
```

### Errors

| Code | error | When |
|------|-------|------|
| 400 | `invalid_value` | out-of-range/invalid field (`{error, field, message}`) |
| 400 | `missing_field` | required JSON field absent |
| 404 | `not_found` | unknown path |
| 405 | `method_not_allowed` | path exists, wrong verb |
| 409 / 503 | reserved | device busy/locked / offline (declared in the REST contract; not synthesized by this dev build) |

## Safety behaviour (enforced in code)

- Constructor and `all_off()` drive every line to its de-asserted (safe) level; `all_off` opens all relays so no output flows regardless of mirrored level.
- Relative `intensity_up/down` are bounded (`MAX_STEPS_PER_CALL = 5`). Absolute `set_intensity(level)` is explicit intent, so it may step the full 0–20 range but never past 20.
- Mode change zeroes that channel's intensity mirror (matches device).

## Off-hardware simulation

The whole stack runs under desktop CPython for testing without the board — `lib/hal.py` swaps in a logging fake `Pin`. `status()["platform"]` reports `simulation (CPython)` there.

> **Dev build has no auth** (binds `0.0.0.0`). Add a bearer-token check in `lib/http_api.py._handle` before using outside a trusted LAN.
