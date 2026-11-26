# Phase 4 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine. No Zipformer, Whisper, or hardware-tier row is claimed here.

## Endpointer (M4.1)

`tests/test_endpoint_policy.py` locks the order. Digit patience runs before `p_complete`. A phone string at 700 ms does not end. The same silence on `none` ends at 800 ms. `p_complete` 0.99 at 300 ms does not end a `phone` slot (`test_digit_patience_beats_high_p_complete`). The 1200 ms non-digit ceiling does not cut `phone`; that slot uses `endpoint_digit_hard_ms` (2000). One `TURN_END` per utterance until the next speech start.

`expected_slot` defaults to `none`.

## Turn-completeness classifier (M4.2)

Encoder: **`from_scratch`**. Hashed character n-grams plus a linear layer. Not a transformer. Plan T4.2.2 STARTING POINT was lr `2e-5`, 3 epochs, batch 32, max length 64 (transformer-scale). This trainer uses `TRAIN_LR=0.1` so the linear weights move. JSON: `docs/results/phase4_train.json`.

| Field | Value |
|---|---|
| Rows | 4000 (2000 fixture sentences × complete + prefix) |
| Held-out accuracy | **1.0000** |
| Fixtures SHA-256 | `a568a5e200fbcbef65ab23fde9ba35070a3c0d81c6e0d303bc73103e65c62371` |
| Export | ONNX + INT8 (`onnxruntime.quantization.quantize_dynamic`) |

Accuracy 1.0 is on synthetic clinic templates. It is not a spoken-eval number.

CPU latency from `uv run python -m evals.bench.turn_latency` (warmup 5, samples 20, `time.perf_counter`):

| Name | Status | p50 ms | p95 ms | Budget |
|---|---|---|---|---|
| `turn_complete` | ok | **0.1425** | 4.2571 | met (TARGET 10 ms) |

JSON: `docs/results/phase4_turn_latency.json`. ADR-007 was **not** opened. `turn_model_enabled` default is **true**. Missing `models/weights/turn_complete.onnx` (gitignored) loads an unavailable scorer and the endpointer uses `p_complete=0`.

A classifier timeout is `p_complete=0`; silence rules still run (`tests/test_turn_pool_timeout.py`).

## Barge-in, backchannels, playback (M4.3)

VAD no longer auto-barges. Gates: `barge_in_enabled`, ≥ 250 ms of speech, stable partial that `is_backchannel` rejects. Default phrases: `mm-hmm,mhm,uh-huh,yeah,ok,okay`. `yes` is not in the default. `okay` on `none` is a backchannel; on `confirm` it is an answer. A backchannel does not increment `turnwise_barge_in_total`.

Playback: 10 frames tagged `ABCDEFGHIJ`, ack 4 → prefix `ABCD` (frames 0–3). Missing map → empty `played_text` and `turnwise_playback_unmap_total`. Ack ahead of sent chunks is ignored and counted.

```
SAY text     A B C D E F G H I J
frame        0 1 2 3 4 5 6 7 8 9
client ack               ^
played_text  A B C D
barge-in     |--- cancel speaking tasks, generation++ ---|
```

## Cancel latency and counters (M4.4)

Synthetic in-process stub sender (`evals/turn/latency.py`). Formula (appendix E): last outbound PCM write minus `barge_in` return; if the last write preceded the return, time until the speaking task stopped.

`uv run pytest tests/test_cancel_latency_synthetic.py::test_stub_cancel_latency_under_100ms -s`

```
cancel_latency_ms=0.0543
```

TARGET 100 ms. The stub path met it.

Counters exist: `turnwise_cancel_latency_seconds`, `turnwise_response_gap_seconds`, `turnwise_early_cutoff_total`, `turnwise_false_barge_in_total`, `turnwise_missed_barge_in_total`. False/missed increment only from labeled fixtures. Response gap is `first_audio_write - turn_end_ts` (monotonic). TTFA still uses the client ack and has no samples. False barge-in **rate** is not estimated from these unit fixtures; that TARGET is phase 9.

## Not run / blocked

| Row | Status |
|---|---|
| Headphone / speaker AEC | not run (phase 2) |
| Zipformer / Whisper finalize | blocked (ADR-006) |
| Hardware tier | blocked (ADR-004) |
| Week-6 SQLite book path | not this phase (phase 6) |
