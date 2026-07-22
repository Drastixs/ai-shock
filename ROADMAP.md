# Roadmap

The system is built in three tiers. **Each tier is independently demoable** — if a later
tier isn't ready, the demo still works from the tier below it. Build in order; don't start
a tier before the one under it fires reliably.

Guiding principle: keep things simple and demoable. Prefer the obvious solution over the
clever one.

## Tier 1 — Hardware loop (foundation)

Prove the physical chain end to end, with a human pressing the button instead of a model.

- ESP32 (Genesis Mini) firmware: SoftAP + raw UDP listener driving the relay board.
- Relay board: ESP32 GPIO → IRLZ44N (flyback diodes on coils) → normally-open relays in series with the electrode leads.
- Web test-fire page: per-channel manual stim + a calibration tool to find each wearer's trigger-finger threshold.
- **Safety hardening lands here:** 500 ms UDP watchdog, per-burst cap (~300 ms) + cooldown, physical kill switch in the lead.

**Demo:** click a channel on the web page → the wearer's finger twitches on command.

**Done when:** stim fires reliably from the web page, and every failure mode (WiFi drop,
power loss, crash) leaves all relays open.

## Tier 2 — Telemetry loop (full loop, no ML)

Close the loop with the game itself as the "vision" source.

- Patch AssaultCube to emit ground-truth enemy screen-space boxes (head + body, vest color) over UDP each frame.
- Decision logic: enemy box overlaps the crosshair → send the FIRE packet to the ESP32.
- This same telemetry hook auto-labels the training data for Tier 3 and remains the ML-free fallback demo path.

**Demo:** enemy walks into the crosshair in-game → the wearer's finger pulls the trigger.
No model involved.

**Done when:** the game → UDP → stim loop fires on real enemies within the muscle's
electromechanical delay budget.

## Tier 3 — Vision loop (headline demo)

Replace the telemetry oracle with a real detector, so the AI is genuinely *seeing* the screen.

- Collect + auto-label data via the Tier 2 telemetry hook (see [`docs/training.md`](docs/training.md)).
- Train YOLO on Modal serverless GPU (see [`modal/README.md`](modal/README.md)); export ONNX.
- Build the TensorRT FP16 engine on the Jetson; run the live per-frame inference loop.
- On-screen bounding-box overlay so the audience sees what the model sees.

**Demo:** the vision model detects enemies live and fires the wearer's finger, with boxes
drawn on screen. The telemetry hook from Tier 2 stays wired as the fallback.

**Done when:** the detector drives the trigger on the held-out map at demo-grade accuracy,
with the overlay visible.

## Out of scope

- Aim-nudge up/down.
- Mouse/software input control — not what this project is about, and less compelling in the demo.

Aim-nudge left/right is a **stretch goal** only after Tier 3 is solid.
