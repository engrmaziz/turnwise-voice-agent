# ADR-003: How the local model stack will be chosen

- Status: Proposed
- Date: 2026-11-25

## Context

The voice path has to produce first audio quickly on consumer hardware, stay fully local, and bias recognition toward clinic names. Several stacks can do parts of this. Picking one before measuring this machine's real-time factor, time-to-first-token, and time-to-first-chunk would freeze a guess into config.

No model name is a default in settings. The packages under `models/` have no worker implementation.

## Decision

A model is eligible for the hot path only when a benchmark on the target hardware shows all of the following:

1. Streaming or a measured finalize latency that fits the stage budget in `docs/ARCHITECTURE.md`. A decoder that waits on a multi-second agreement window does not fit the 700 ms time-to-first-audio target.
2. Contextual biasing (hotwords or an equivalent context graph) is actually available in the pinned build. A model whose streaming mode is greedy-only does not satisfy the doctor-name requirement until that build grows a biasing path we have run.
3. A CPU fallback exists for TTS, and for ASR if the GPU is busy with the language model. Pools are process-wide, not one model instance per call.
4. The license allows local redistribution with the repo's download script.
5. The measured contribution to time-to-first-audio is reported in `docs/benchmarks.md` (that file does not exist yet). Phrase-cache hits are a separate row from cold synthesis.

Candidates may be benchmarked. Naming them here does not select them:

- Streaming Zipformer via sherpa-onnx, and a Whisper build with a local-agreement policy, for ASR.
- Silero VAD for endpoint energy.
- A WFST inverse-text-normalization grammar, plus a separate deterministic date resolver. Normalization and "next Tuesday" are different problems.
- A small ONNX encoder for turn completion and for joint intent and slots.
- A 3B–8B instruct model served with grammar-constrained decoding, for proposals and FAQ answers only (ADR-001).
- Kokoro and Piper for speech synthesis.

NeMo text processing does not install from pip on native Windows because of Pynini. Benchmarks that need it run in WSL2 or the Compose image, not in a bare Windows venv.

## Consequences

- Phase 1 ends when `docs/benchmarks.md` has numbers from this hardware, not when a dependency was added.
- This ADR moves to Accepted only in a follow-up that records the chosen builds, their versions, and the measured numbers.
- Emotion models are out of the critical path. Dialogue signals (repair count, repeated refusals, barge-in) are the fallback when an audio classifier times out.
