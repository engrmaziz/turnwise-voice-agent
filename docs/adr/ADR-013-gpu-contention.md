# ADR-013: GPU contention strategy

- Status: Accepted
- Date: 2026-11-27

## Context

M10.2 measures three contention strategies on the same host: CPU TTS (strategy A, already ADR-010), an LLM priority queue with speaking sessions first (strategy B), and `llm_max_batch` 1 versus 4 (strategy C). The pick is the p95 of `turnwise_ttfa_seconds` at the load knee, not tokens/s.

JSON: `docs/results/phase10_load_piper.json` (A) plus `phase10_load_piper_b.json` / `phase10_load_piper_c.json`. Path: `ttfa_path=piper_play_ack`. `product_quote=false` (ADR-012: synthetic TURN_END plus scripted NLU, not a realtime call). p95 is a Prometheus histogram bucket upper bound. A row is a miss when any session produces no play-ack (`sessions_acked < n`) or when bucket p95 exceeds 1.2 s.

This host, `Windows-10-10.0.26300-SP0`, `tts_timeout_ms` 800, one CPU Piper worker, Ollama `qwen3.5:4b` on B/C:

- A (no LLM, Piper only): n=1 `sessions_acked=1`, `ttfa_p95_s=1.2`, status `hit`; n=2 miss (`sessions_without_play_ack`); **knee 1**
- B (ollama paraphrase, `llm_max_batch=1`): n=1 `ttfa_p95_s=2.0`, status `miss` (`over_cap`); **knee 0**
- C (ollama paraphrase, `llm_max_batch=4`): n=1 `ttfa_p95_s=2.0`, status `miss` (`over_cap`); **knee 0**

Paraphrase on SAY adds LLM TTFT before the first Piper chunk. That moved histogram p95 from the 1.2 s bucket to the 2.0 s bucket at n=1.

## Decision

Pick **strategy A: CPU Piper**. It is the only synthesizer play-ack column whose n=1 histogram p95 is still at or under the 1.2 s cap.

- TTS on **CPU** (ADR-010). Default `tts_backend` stays empty for CI. Load `--tts-backend piper` is the measured A column.
- Speaking LLM jobs still enqueue at priority 0. **Strategy B was measured** and missed the cap (`over_cap` at 2.0 s).
- `llm_max_batch` stays **1**. **Strategy C was measured** at batch 4 and also missed (`over_cap` at 2.0 s). Batch 4 did not recover the cap.

The knee **1** is capacity of one CPU Piper worker under the 800 ms synth timeout. It is not a concurrent-user marketing number and is not a product SLO.

Stub play-ack knee 16 remains in `docs/results/phase10_load.md` and must not be mixed with this column.

## Consequences

- ADR-003 is Accepted with named Zipformer / Piper / Ollama builds. Defaults stay empty.
- Do not invent a B/C winner from identical stub-LLM columns. These B/C rows used live Ollama paraphrase.
- README load cells cite the JSON files and keep `product_quote=false` in view.
