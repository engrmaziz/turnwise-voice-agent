# ADR-006: ASR backend

- Status: Proposed
- Date: 2026-11-26

## Context

Phase 3 must name Zipformer or Whisper plus LocalAgreement-2 from measured finalize p50 on this machine. A copied number from a paper is not a measurement.

JSON: `docs/results/phase3_asr_compare.json`

## Decision

The ASR backend is **blocked**. Both ASR backends are blocked; asr_backend stays empty. `TURNWISE_ASR_BACKEND` stays empty so the call path uses the stub. ADR-003 stays Proposed.

## Consequences

- The sample env file records the chosen value, which is empty while blocked.
- Hotword entity WER is a separate JSON; an `unsupported` on-row is not a zero.
- ADR-003 stays Proposed until TTS and LLM rows are also chosen.
