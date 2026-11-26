# ADR-013: GPU contention strategy

- Status: Proposed
- Date: 2026-11-26

## Context

M10.2 measures three contention strategies on the same host: CPU TTS (strategy A, already ADR-010), an LLM priority queue with speaking sessions first (strategy B), and `llm_max_batch` 1 versus 4 (strategy C). The pick is the p95 of `turnwise_ttfa_seconds` at the load knee, not tokens/s.

The load driver now stamps a synthetic TURN_END, runs dialogue→chunker→TN→stub audio_out, and acks play index 0 (`evals/play_path.py`). JSON: `docs/results/phase10_load.json`. That path is labeled `ttfa_path=stub_play_ack` and `product_quote=false`. ADR-012 still forbids quoting it as product TTFA. ADR-004's hardware tier is still **blocked**. p95 is a Prometheus histogram bucket upper bound (`ttfa_p95_source=histogram_bucket`).

This host, `Windows-10-10.0.26300-SP0`, `load_n_max` 16:

- n=1..12: `ttfa_p95_s=0.05`, status `hit`
- n=13..16: `ttfa_p95_s=0.1`, status `hit`
- `knee`: 16, `reason`: `largest_n_at_or_under_cap`

## Decision

No strategy is chosen from this p95 column. It is silence-stub play-ack, not a synthesizer p95 (ADR-010). Tokens/s was not used as a substitute.

Defaults that remain in force until a **real TTS** play-ack load fills p95:

- TTS on **CPU** (ADR-010 names Piper). Default `tts_backend` stays empty (silence stub) so this load column stays labeled stub.
- Speaking LLM jobs enqueue at priority 0, idle jobs at 1. That queue exists; it is not a p95 winner.
- `llm_max_batch` stays **1**. Batch 4 was not measured against a real-TTS TTFA p95.

The knee 16 is capacity under the stub play-ack path at `load_n_max`. It is not a concurrent-user marketing number and is not a product SLO.

## Consequences

- ADR-003 stays Proposed. ASR, LLM, and TTS rows are still unnamed builds.
- A later load with Piper or Kokoro play-acks rewrites this ADR from that JSON's p95 column.
- README load cells cite `docs/results/phase10_load.md` and must keep `product_quote=false` in view.
