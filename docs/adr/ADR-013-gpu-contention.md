# ADR-013: GPU contention strategy

- Status: Proposed
- Date: 2026-11-26

## Context

M10.2 measures three contention strategies on the same host: CPU TTS (strategy A, already ADR-010), an LLM priority queue with speaking sessions first (strategy B), and `llm_max_batch` 1 versus 4 (strategy C). The pick is the p95 of `turnwise_ttfa_seconds` at the load knee, not tokens/s.

The load driver is the scripted caller (`evals/load.py`). Scripted NLU inject does not play-ack, so the TTFA histogram has zero samples. A histogram with zero samples is a miss, not a guessed p95. ADR-004's hardware tier is still **blocked**. JSON: `docs/results/phase10_load.json`.

## Decision

No strategy is chosen from a p95 column, because that column is empty (`ttfa_p95_s: null`, `reason: no_play_ack_samples`). Tokens/s was not used as a substitute.

Defaults that remain in force until a play-ack load run fills p95:

- TTS on **CPU** (ADR-010). `tts_backend` stays empty (silence stub).
- Speaking LLM jobs enqueue at priority 0, idle jobs at 1. That queue exists; it is not a p95 winner.
- `llm_max_batch` stays **1**. Batch 4 was not measured against a real TTFA p95.

The knee is `n=0 failed at 1` on this host. That is capacity under the scripted path, not a concurrent-user marketing number.

## Consequences

- ADR-003 stays Proposed. ASR, LLM, and TTS rows are still unnamed builds.
- A later realtime load with play-acks rewrites this ADR from the new JSON's p95 column.
- README load cells cite `docs/results/phase10_load.md` and must not invent a passing N.
