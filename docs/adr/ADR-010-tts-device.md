# ADR-010: TTS device

- Status: Accepted
- Date: 2026-11-26

## Context

Phase 7 streams PCM from a process-wide TTS pool. T1.4.4's JSON row for first-chunk p50 is **ok** (`docs/results/bench/20261126T175404Z.json`, also `docs/benchmarks.md`). The 8 GB hardware tier in the front matter pins TTS to CPU so a later GPU LLM keeps the card. T7.4.4 is not allowed to flip that default from a single-call bench. M10.2 is the contention measurement.

This host has an NVIDIA GPU (`nvidia-smi` present in `docs/benchmarks.md`). That does not make a GPU TTS default.

## Decision

TTS runs on **CPU**. The named synthesizer is **piper-tts 1.8.0** with voice **en_US-amy-low** (`use_cuda=false`). First-chunk p50 is **33.9 ms**, p95 **39.1 ms** (warmup 5, samples 20, text `Hello this is Turnwise.`, output 16 kHz). That is inside the 200 ms TARGET. GPU TTS (`tts.first_chunk.gpu`) remains `blocked` (`model_layout_unpinned`). Kokoro is not named: CPU hit the TARGET, so there is no swap.

`TURNWISE_TTS_BACKEND` **defaults empty**, so CI and a weight-free checkout keep the silence stub. Operators who ran `uv sync --extra tts` and `python scripts/download_models.py` set `TURNWISE_TTS_BACKEND=piper`. A missing ONNX keeps `/health` 200 with `degraded_tts` true.

In-process stub numbers (not a model p50), from `tests/test_tts_stub_latency.py` writing `docs/results/phase7_stub.json`:

| Row | p50 ms | p95 ms |
|---|---|---|
| Phrase-cache hit | 0.0038 | 0.0106 |
| Stub first-chunk synth | 0.1145 | 0.2414 |

Those are silence-stub wall times. They are not the synthesizer row above.

## Consequences

- Warmup phrases (greeting, fillers, `cannot_speak`) skip the pool on the hot path. Cache-hit p50 is under 5 ms in-process.
- Content TTFA on a call still needs play-ack through this synthesizer. Stub load p95 is not a product quote (ADR-013).
- ADR-003 stays Proposed until ASR and LLM rows are also `ok`.
- ADR-004 stays blocked (ASR finalize and LLM TTFT missing in the same JSON).
- Revisit this ADR if a later CPU row misses 200 ms, or when M10.2 measures GPU contention against a synthesizer play-ack p95.
