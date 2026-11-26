# Phase 10 load

Numbers are copied from JSON. TTFA p95 is not invented when play-ack count is 0.

- `platform`: Windows-10-10.0.26300-SP0
- `adr004_tier`: blocked
- `knee`: 0
- `reason`: n=0 failed at 1

| n | ttfa_samples | ttfa_p95_s | status | elapsed_s |
|---|---|---|---|---|
| 1 | 0 | None | miss | 0.040917399994214065 |
| 2 | 0 | None | miss | 0.07302979999803938 |

## Contention (ADR-013)

Copied from the same JSON. The pick is p95, not tokens/s. Every p95 cell is empty because play-ack count is 0.

| Strategy | What ran | ttfa_p95_s |
|---|---|---|
| A CPU TTS | ADR-010 default, `tts_backend` empty (silence stub) | None |
| B LLM priority queue | speaking jobs priority 0, idle 1 (`tests/test_llm_priority.py`) | None |
| C `llm_max_batch` 1 vs 4 | default remains 1; no play-ack p95 for either cap | None |

ADR-013 stays Proposed. GPU: `no_gpu_smi_on_event_loop`.
