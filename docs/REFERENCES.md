# Reference documents

Place or link all hardware documentation here so the agent can read it in-repo.

## Required (add to this folder)

| Document | Filename | Notes |
|----------|----------|-------|
| AUVON AS8016 user manual | `AUVON-AS8016-5languages-sms-V1.0-211014-80x130mm.pdf` | Primary TENS unit reference — button layout, channels A/B, outputs A1/A2/B1/B2, modes P01–P24, timing, intensity |
| Axiometa Genesis Mini schematic | *(download from [axiometa.io](https://www.axiometa.io/products/axiometa-genesis-mini))* | AX22 port pinout, power, USB |

## Online mirrors (if local PDF is missing)

- AUVON AS8016 quick guide (newer revision): https://cdn.shopifycdn.net/s/files/1/0260/2152/7631/files/AUVON-US-AS8016-sms-v1.6-221116-75x130mm.pdf
- Axiometa Genesis Mini product page: https://www.axiometa.io/products/axiometa-genesis-mini
- ESP32-S3-Mini-1 datasheet: https://www.espressif.com/sites/default/files/documentation/esp32-s3-mini-1_mini-1u_datasheet_en.pdf
- MicroPython ESP32-S3 firmware: https://micropython.org/download/ESP32_GENERIC_S3/
- Arduino variant (official GPIO map): https://github.com/espressif/arduino-esp32/tree/master/variants/axiometa_genesis_mini

## AUVON AS8016 — control surface summary

From the manual, the front-panel controls we are automating:

| Control | Manual label | Function |
|---------|--------------|----------|
| Mode | M (⑥) | Cycle TENS modes P01–P16 or EMS P17–P24 for selected channel |
| Timer | Time (⑦) | Adjust session timer (default 20 min, range 10–90 min) |
| Channel | Center / A·B (⑮) | Select channel A (A1+A2) or B (B1+B2) |
| Intensity + | + (⑭) | Increase intensity for selected channel |
| Intensity − | − (⑯) | Decrease intensity for selected channel |

Outputs: four jacks — **A1, A2** (parallel, channel A) and **B1, B2** (parallel, channel B). A and B are galvanically isolated.
