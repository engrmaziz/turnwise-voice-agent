# Phase 10 load

TTFA is stub play-ack (`ttfa_path=stub_play_ack`). It is not a product SLO quote.
p95 is a Prometheus histogram bucket upper bound. ADR-004 stays blocked.

- `platform`: Windows-10-10.0.26300-SP0
- `adr004_tier`: blocked
- `knee`: 16
- `reason`: largest_n_at_or_under_cap
- `ttfa_path`: stub_play_ack
- `product_quote`: False

| n | ttfa_samples | ttfa_p95_s | status | elapsed_s |
|---|---|---|---|---|
| 1 | 4 | 0.05 | hit | 0.042070800001965836 |
| 2 | 8 | 0.05 | hit | 0.07440359999600332 |
| 3 | 12 | 0.05 | hit | 0.11779430000751745 |
| 4 | 16 | 0.05 | hit | 0.16878320000250824 |
| 5 | 20 | 0.05 | hit | 0.20089249999728054 |
| 6 | 24 | 0.05 | hit | 0.24197740000090562 |
| 7 | 28 | 0.05 | hit | 0.29147930000908673 |
| 8 | 32 | 0.05 | hit | 0.31019810000725556 |
| 9 | 36 | 0.05 | hit | 0.33956140000373125 |
| 10 | 40 | 0.05 | hit | 0.36444390000542626 |
| 11 | 44 | 0.05 | hit | 0.39858530000492465 |
| 12 | 48 | 0.05 | hit | 0.44506639998871833 |
| 13 | 52 | 0.1 | hit | 0.491799199997331 |
| 14 | 56 | 0.1 | hit | 0.5405326000036439 |
| 15 | 60 | 0.1 | hit | 1.2289369999925839 |
| 16 | 64 | 0.1 | hit | 0.5992130999948131 |

## Contention (ADR-013)

Stub play-ack p95 is not a synthesizer p95 (ADR-010). ADR-013 does not pick A/B/C from this column. Tokens/s is not used.
