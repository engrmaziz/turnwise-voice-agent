# ADR-006: ASR backend

- Status: Accepted
- Date: 2026-11-27

## Context

Phase 3 must name Zipformer or Whisper plus LocalAgreement-2 from measured finalize p50 on this machine. A copied number from a paper is not a measurement.

JSON: `docs/results/phase3_asr_compare.json`

## Decision

The ASR backend is **zipformer**. zipformer finalize p50 is 173.7 ms. Finalize p50 173.7 ms misses the 100 ms TARGET.

## Consequences

- Default `TURNWISE_ASR_BACKEND` stays empty so CI stays weight-free. Operators set it to the chosen backend after `uv sync --extra asr` and `python scripts/download_models.py`.
- Hotword entity WER is a separate JSON; an `unsupported` on-row is not a zero.
- ADR-003 is Accepted. LLM TTFT is in `docs/benchmarks.md`. Default `asr_backend` stays empty.
