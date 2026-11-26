# Phase 1 results

## Headphone check (T1.3.4)

Status: not run. Fill this row on a real browser with headphones. Do not mark pass without doing it.

| Browser | AEC from `getSettings()` | NS from `getSettings()` | Frame counter increased | Result |
|---|---|---|---|---|
| | | | | not run |

## Tone round trip (T1.3.5)

Covered by `tests/test_ws_audio.py`. The number of frames accepted and the play-ack cursor are assertions, not a latency claim.

## Hardware bench (M1.4)

`python -m evals.bench` writes `docs/results/bench/<utc>.json`, regenerates `docs/benchmarks.md`, and rewrites ADR-004 from that JSON. Latest JSON: `docs/results/bench/20261126T200406Z.json`. Zipformer finalize p50 **32.4 ms**, Ollama `qwen3.5:4b` TTFT grammar-on p50 **57.2 ms**, Piper first-chunk p50 **34.5 ms**. ADR-004 names **16 GB+** (RTX 3090 24 GB). Default backends stay empty. The GPU TTS row is `blocked` (`model_layout_unpinned`). The 10 ms sleep timer is `tests/test_bench_harness.py`, not a model.
