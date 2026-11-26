# ADR-013: GPU contention strategy

- Status: Accepted
- Date: 2026-11-27

## Context

M10.2 measures three contention strategies on the same host: CPU TTS (strategy A, already ADR-010), an LLM priority queue with speaking sessions first (strategy B), and `llm_max_batch` 1 versus 4 (strategy C). The pick is the p95 of `turnwise_ttfa_seconds` at the load knee, not tokens/s.

JSON: `docs/results/phase10_load_piper.json`. Path: `ttfa_path=piper_play_ack`. `product_quote=false` (ADR-012: this is still a synthetic TURN_END plus scripted NLU, not a realtime call). p95 is a Prometheus histogram bucket upper bound. ADR-004 stays **blocked**. A row is a miss when any session produces no play-ack (`sessions_acked < n`) or when bucket p95 exceeds 1.2 s.

This host, `Windows-10-10.0.26300-SP0`, `tts_timeout_ms` 800, one CPU Piper worker:

- n=1: `sessions_acked=1`, `ttfa_p95_s=1.0`, status `hit`
- n=2: `sessions_acked=1`, status `miss` (`sessions_without_play_ack`)
- n=3: `sessions_acked=1`, status `miss`
- `knee`: 1, `reason`: `largest_n_at_or_under_cap`

The second session hits `TtsTimeoutError` waiting on the single ONNX worker. That is the contention signal.

## Decision

Pick **strategy A: CPU Piper**. It is the only synthesizer play-ack p95 column.

- TTS on **CPU** (ADR-010). Default `tts_backend` stays empty for CI. Load `--tts-backend piper` is the measured column.
- Speaking LLM jobs still enqueue at priority 0. That queue is not a p95 winner: **strategy B is blocked** (`llm_unavailable`).
- `llm_max_batch` stays **1**. **Strategy C is blocked** (`llm_unavailable`). Batch 4 was not measured against a synthesizer TTFA p95.

The knee **1** is capacity of one CPU Piper worker under the 800 ms synth timeout at `load_n_max` 16. It is not a concurrent-user marketing number and is not a product SLO.

Stub play-ack knee 16 remains in `docs/results/phase10_load.md` and must not be mixed with this column.

## Consequences

- ADR-003 stays Proposed. ASR and LLM rows are still unnamed.
- A later load with a live LLM rewrites B and C from that JSON. Do not invent a B/C winner from identical stub-LLM columns.
- README load cells cite both JSON files and keep `product_quote=false` in view.
