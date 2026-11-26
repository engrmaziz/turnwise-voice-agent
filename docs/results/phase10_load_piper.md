# Phase 10 load

TTFA is `piper_play_ack`. It is not a product SLO quote (ADR-012).
p95 is a Prometheus histogram bucket upper bound. ADR-004 stays blocked.

- `platform`: Windows-10-10.0.26300-SP0
- `adr004_tier`: blocked
- `knee`: 1
- `reason`: largest_n_at_or_under_cap
- `ttfa_path`: piper_play_ack
- `product_quote`: False
- `tts_backend`: piper:en_US-amy-low.onnx

| n | sessions_acked | ttfa_samples | ttfa_p95_s | status | elapsed_s |
|---|---|---|---|---|---|
| 1 | 1 | 4 | 1.0 | hit | 3.1921111999981804 |
| 2 | 1 | 4 | 1.0 | miss | 1.4203258999914397 |
| 3 | 1 | 4 | 1.0 | miss | 1.3928696999937529 |

## Contention (ADR-013)

- pick: `A`
- reason: CPU Piper play-ack is the only synthesizer p95 column. B and C need an LLM TTFT row to move TTFA.
- `cpu_piper`: ok, p95=1.0s knee=1
- `llm_speaking_priority`: blocked (llm_unavailable)
- `llm_max_batch_4`: blocked (llm_unavailable)
