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
- `llm_backend`: unavailable
- `llm_max_batch`: 1

| n | sessions_acked | ttfa_samples | ttfa_p95_s | status | elapsed_s |
|---|---|---|---|---|---|
| 1 | 1 | 4 | 1.2 | hit | 3.4413778000161983 |
| 2 | 1 | 4 | 1.0 | miss | 1.3794235000095796 |
| 3 | 1 | 4 | 1.0 | miss | 1.3937564000079874 |

## Contention (ADR-013)

- pick: `A`
- reason: lowest knee histogram p95 is A at 1.2s
- `cpu_piper`: ok, p95=1.2s knee=1
- `llm_speaking_priority`: ok, n=1 p95=2.0s over_cap, knee=0 (Ollama paraphrase)
- `llm_max_batch_4`: ok, n=1 p95=2.0s over_cap, knee=0 (Ollama paraphrase)
