# ADR-003: How the local model stack will be chosen

- Status: Accepted
- Date: 2026-11-27

## Context

The voice path has to produce first audio quickly on consumer hardware, stay fully local, and bias recognition toward clinic names. Eligibility still requires the five criteria below. This follow-up names the builds that met them on this host. Default settings stay empty so CI is weight-free.

## Decision

Hot-path names (operators opt in with env vars; defaults stay empty):

| Role | Build | Evidence |
|---|---|---|
| ASR | sherpa-onnx 2.0.3 streaming Zipformer2 int8 `en-2023-06-26`, `modified_beam_search`, SentencePiece `bpe.model` vocab, `hotword_score=2.0` | ADR-006; entity WER JSON `docs/results/phase3_entity_wer.json` |
| TTS | piper-tts 1.8.0 `en_US-amy-low` CPU | ADR-010 |
| LLM | Ollama `qwen3.5:4b`, JSON-schema `format`, `think: false` | `docs/benchmarks.md` TTFT grammar-on p50 57.2 ms |
| VAD | Silero ONNX | locked in `models/lock.toml` |

Whisper+LA-2 (`faster-whisper` 1.2.1 `tiny.en` CPU int8) is an ablation, not the hot path: north-wind finalize p50 **490.8 ms** / p95 **529.8 ms**, last-window LA-2 delay **476.8 ms** (`docs/results/phase3_whisper.json`). That is not a 100 ms streaming budget.

Criteria:

1. Zipformer is streaming. Compare finalize p50 173.7 ms still misses the 100 ms TARGET; Whisper LA-2 is slower. Zipformer stays the ASR name.
2. Hotwords run on this pinned build (`modified_beam_search` + uppercase BPE phrases from the locked `bpe.model`). Entity error rate **0.733** (22/30) with bias off and **0.700** (21/30) with the roster as phrases at `hotword_score=2.0`. Sweep 1.0 / 1.5 / 2.0: only 2.0 moved a hypothesis (`JONAH HA` → `JONAH HALE`). JSON: `docs/results/phase3_entity_wer.json`.
3. TTS and ASR both have CPU pools. Process-wide, not per call.
4. Lock URLs in `models/lock.toml` cover Zipformer, Piper, Silero, and faster-whisper `tiny.en`.
5. `docs/benchmarks.md` has ASR finalize, LLM TTFT, and TTS first-chunk `ok` cells.

Env: `TURNWISE_ASR_BACKEND=zipformer`, `TURNWISE_TTS_BACKEND=piper`, `TURNWISE_LLM_BACKEND=ollama` after `uv sync --extra tts --extra asr --extra whisper` and `python scripts/download_models.py`.

## Consequences

- Emotion stays off the critical path (ADR-011) until 30 scored call-like labels exist.
- ADR-004 remains Proposed on the hardware-tier ADR itself; the machine is 16 GB+ from nvidia-smi, not from this file.
- A blocked cell is still not a measurement.
