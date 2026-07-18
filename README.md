# Neuromuscular Aim Assistant

An AI that plays Assault Cube *through a human's arm* by electrically stimulating
their muscles. See `CLAUDE.md` for the full project summary, signal chain, and
safety invariants, and `ROADMAP.md` for the build plan.

## Docs
- [`CLAUDE.md`](CLAUDE.md) — project summary, class scheme, signal chain, safety invariants.
- [`training.md`](training.md) — vision model / data-collection pipeline.
- [`cheat-loop/`](cheat-loop/) — the live inference loop on the Jetson (capture → detect → target → stim). See [`cheat-loop/loop-design.md`](cheat-loop/loop-design.md) for the full design.
- [`ideas-shock.md`](ideas-shock.md) — second-module stim feature ideas (hit-feedback shock, recoil kick, fine-mode aim, etc.).
