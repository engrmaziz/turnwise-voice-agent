# ADR-010: TTS device

- Status: Accepted
- Date: 2026-11-26

## Context

Phase 7 streams PCM from a process-wide TTS pool. T1.4.4's JSON row for first-chunk p50 is **blocked** (`missing_tts:import_piper,import_kokoro`). The 8 GB hardware tier in the front matter pins TTS to CPU so a later GPU LLM keeps the card. T7.4.4 is not allowed to flip that default from a single-call bench. M10.2 is the contention measurement.

This host has an NVIDIA GPU (`nvidia-smi` present in `docs/benchmarks.md`). That does not make a GPU TTS default.

## Decision

TTS runs on **CPU**. `TURNWISE_TTS_BACKEND` stays empty, so the call path uses the silence stub of known duration. Piper and Kokoro first-chunk p50 are unpublished. GPU TTS is a rejected option until M10.2 has a P95 row and a CPU miss is a measured number, not a guess.

In-process stub numbers (not a model p50), from `tests/test_tts_stub_latency.py` writing `docs/results/phase7_stub.json`:

| Row | p50 ms | p95 ms |
|---|---|---|
| Phrase-cache hit | 0.0038 | 0.0106 |
| Stub first-chunk synth | 0.1145 | 0.2414 |

Those are silence-stub wall times. They do not satisfy the 200 ms TARGET for a real synthesizer.

## Consequences

- Warmup phrases (greeting, fillers, `cannot_speak`) skip the pool on the hot path. Cache-hit p50 is under 5 ms in-process.
- Content TTFA on a cold real model remains unmet. The stub does not stand in for Kokoro or Piper.
- ADR-003 stays Proposed until ASR, LLM, and TTS rows are chosen from measured `ok` cells.
- Revisit this ADR when `evals/bench/tts.py` writes an `ok` CPU row, or when M10.2 measures GPU contention.
