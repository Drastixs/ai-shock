# Neuromuscular Aim Assistant

An AI that plays [AssaultCube](https://assault.cubers.net/) *through a human's arm* — a
vision model detects an enemy on screen and electrically stimulates the wearer's forearm
so their own finger pulls the trigger.

Built at the Axiometa × Anthropic × Bambu Lab × ElevenLabs × Seedcamp hardware hackathon.
Concept reference: [Mr Homeless](https://www.youtube.com/watch?v=9alJwQG-Wbk).

> **Safety-critical hardware.** This project drives a TENS unit against a person's muscles.
> Read the [Safety](#safety) section before wiring or powering anything. Every design
> decision here defers to the safety invariants — they are non-negotiable.

## The demo

The crosshair passes over an enemy → the vision model fires a UDP command → a relay closes
→ a TENS burst contracts the wearer's trigger finger. Aim-nudge left/right is a stretch
goal; up/down is out of scope.

## How it works

The whole system runs on a single self-hosted access point (no venue WiFi, no cloud in the
loop) and moves in one direction: pixels → detection → UDP → muscle.

| Stage | Hardware | Role |
|-------|----------|------|
| **See** | Jetson Orin Nano | Runs the game (compiled ARM64) + a YOLO/TensorRT enemy detector. A UDP telemetry hook patched into the game auto-labels training data and provides an ML-free fallback path. |
| **Decide** | — | An enemy box overlapping the crosshair above threshold → `FIRE`. One raw UDP packet is sent to the controller. |
| **Act** | Axiometa Genesis Mini (ESP32-S3) | Receives the UDP command as its own SoftAP and drives the relay board. Firmware enforces burst limits, cooldown, and a watchdog. |
| **Stimulate** | Relay board + AUVON 4-channel TENS | Mechanical relays sit in series with the electrode leads. The TENS unit stays battery-powered and fully floating for galvanic isolation. |

## Safety

These invariants are non-negotiable and double as the demo narration:

- **Normally-open relays** — any crash, power loss, or WiFi drop leaves every output open. The default state is *off*.
- **Firmware watchdog** — no UDP packet for 500 ms opens all relays. Bursts are capped (~300 ms) with a forced cooldown.
- **Physical kill switch** in the electrode lead, held by the wearer at all times.
- **Current never crosses the chest** — electrodes are placed on a single forearm only.

## Repository layout

```
.
├── README.md          You are here — project overview
├── ROADMAP.md         Build order and milestones
├── docs/              Reference material
│   ├── training.md              Vision-model data → training → deploy pipeline
│   ├── API.md                   Control API (Python module + HTTP) for the TENS controller
│   ├── AUVON-AS8016-API.html    REST contract (source of truth for the API)
│   └── AUVON-AS8016-datasheet.pdf
├── modal/             Serverless GPU training (Modal) for the YOLO detector
└── .agent/            Instructions for AI coding agents working in this repo
```

## Getting started

The build is staged so each tier is independently demoable — see [ROADMAP.md](ROADMAP.md)
for the full plan and current status.

- **Train the detector** — see [`modal/README.md`](modal/README.md) and [`docs/training.md`](docs/training.md).
- **Drive the hardware** — see [`docs/API.md`](docs/API.md) for the Python and HTTP control surface.

## Hardware references

- Axiometa Genesis Mini (ESP32-S3-MINI-1) — https://www.axiometa.io/products/axiometa-genesis-mini
- AUVON AS8016 4-channel TENS — datasheet in [`docs/`](docs/AUVON-AS8016-datasheet.pdf)

## For contributors and AI agents

Project conventions, design principles, and working guidelines live in
[`.agent/AGENTS.md`](.agent/AGENTS.md) (symlinked as `CLAUDE.md` for tools that expect it).
