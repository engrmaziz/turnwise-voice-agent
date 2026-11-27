# Phase 9 results

Numbers below are copied from JSON keys. Virtual-clock task success is not a SLO quote.
Realtime TTFA is the only TTFA that may be quoted; this run did not invent it.

## Matrix

- `n`: 9
- `requested_n`: 9
- `elapsed_s`: 0.4467299000098137
- `time_scale`: 0.0
- `clock`: virtual
- `task_success`: 0.8888888888888888

## Smoke

- `n`: 10
- `task_success`: 0.9
- `slot_f1_gate`: forbidden_until_golden_published

## Realtime

JSON: `docs/results/phase9_realtime.json`. Wall-clock 20 ms PCM, energy-VAD (Silero path disabled for this driver so the endpointer can fire), stub TTS. `product_quote=false` (ADR-012: stub play-ack is not a product SLO).

- `status`: ok
- `n`: 30
- `requested_n`: 30
- `clock`: realtime
- `pace_s`: 0.02
- `sessions_acked`: 30
- `ttfa_samples`: 30
- `ttfa_p95_s`: 0.05 (histogram bucket)
- `ttfa_path`: stub_play_ack
- `vad`: energy_fallback

## Ablations

- `endpoint`: status=`blocked` n=`0`
- `bias`: status=`unsupported` n=`0`
- `nlu`: status=`blocked` n=`0`
- `fsm`: status=`ok` n=`1`
- `asr`: status=`blocked` n=`0`
