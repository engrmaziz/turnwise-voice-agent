# Phase 1 results

## Headphone check (T1.3.4)

Status: not run. Fill this row on a real browser with headphones. Do not mark pass without doing it.

| Browser | AEC from `getSettings()` | NS from `getSettings()` | Frame counter increased | Result |
|---|---|---|---|---|
| | | | | not run |

## Tone round trip (T1.3.5)

Covered by `tests/test_ws_audio.py`. The number of frames accepted and the play-ack cursor are assertions, not a latency claim.

## Hardware bench (M1.4)

`python -m evals.bench` writes `docs/results/bench/<utc>.json`, regenerates `docs/benchmarks.md`, and rewrites ADR-004 from that JSON. Model rows stay `blocked` until weights and binaries exist. The GPU TTS row is `not_present` when `nvidia-smi` fails. The 10 ms sleep timer is `tests/test_bench_harness.py`, not a model.
