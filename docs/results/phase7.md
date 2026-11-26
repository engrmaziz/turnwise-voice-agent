# Phase 7 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine. No Piper or Kokoro first-chunk p50 is claimed. TTS weights were not downloaded.

## Entry criteria

| Gate | Status |
|---|---|
| M6.2 template id + confirmed slots | met (Phase 6) |
| T6.3.4 paraphrase cap 180 | met |
| T4.3.3 `PlaybackCursor.note_chunk` | met. Audio-out is the first production caller. |
| T1.4.4 TTS JSON | **blocked**. `missing_tts:import_piper,import_kokoro`. Stub silence of known duration is the pool. |

## M7.1 Templates and paraphrase

Every FSM action in `dialogue/actions.py` has a row in `dialogue/templates.toml`. A missing key fails `load_templates()` at process start. Pending slots render empty; `ask_slot` uses the ask variant. A paraphrase that drops `Dr. Khan` after TN is discarded (`tests/test_paraphrase_slots.py`). Reasons: `length`, `missing_slot`.

## M7.2 Chunker

`Dr.`, `Mr.`, `Mrs.`, `Ms.`, `St.`, `e.g.`, `i.e.`, `p.m.`, `a.m.` are not split points. A 4-word comma flushes on the first chunk and not later. A 20-word clause with no boundary flushes after a fake clock advances 400 ms (`tests/test_chunker.py`). Not `asyncio.sleep(0.4)` as the only proof.

First-chunk exhibit (stub WAVs, silence of known duration, not a spoken model):

| File | Text |
|---|---|
| `docs/results/phase7_first_chunk.wav` | `Dr. Khan can see you,` |
| `docs/results/phase7_full_sentence.wav` | `Dr. Khan can see you, Wednesday at three p.m. Please arrive ten minutes early.` |

## M7.3 TTS normalization

TN is the inverse of ITN. No LLM import in `pipeline/stages/tts_norm.py`.

| Input | Spoken form |
|---|---|
| `14:30` | contains `two`, `thirty`, `p.m.` |
| `5550100` | seven spoken digits |
| `Dr. Khan` | starts with `Doctor` |
| unknown name char | `symbol`, `turnwise_tn_unknown_char_total` |
| confirm context | inserts a comma (no SSML break on the stub) |

Digit mode sets `TtsJob.speed` to `tts_digit_speed` 0.85 STARTING POINT.

## M7.4 Cache, frames, TTFA, device

Play frames are 20 ms / 320 samples (640 bytes). Play acks are `0x03` + length + JSON `{stream, frame_index}`. A 4-byte-only ack is `ack_missing_stream`. Capture acks (`stream=cap`) increment `turnwise_play_ack_wrong_stream_total` and do not move `PlaybackCursor`.

Phrase cache is process-local RAM, not Redis. Warmup ids: greeting, `one_moment`, `could_you_repeat`, `headphones_required`, `seek_emergency`, `cannot_book_now`, `cannot_speak`, `goodbye`. A second lookup does not call the pool. A runtime miss on a warmup phrase increments `turnwise_tts_cache_miss_warmup_total`.

JSON: `docs/results/phase7_stub.json` written by `tests/test_tts_stub_latency.py`.

| Field | Value |
|---|---|
| samples | 20 |
| cache_hit_p50_ms | **0.0038** |
| cache_hit_p95_ms | **0.0106** |
| stub_first_chunk_p50_ms | **0.1145** |
| stub_first_chunk_p95_ms | **0.2414** |
| kokoro_piper | blocked |

Cache-hit p50 is under 5 ms in-process. Stub synth p50 is not a Kokoro/Piper number and does not meet or miss the 200 ms TARGET.

TTFA histograms observe on **play-ack**, not socket write (`tests/test_ttfa_observe.py`). Filler then content: two different samples. Content-only: two equal samples. Count is > 0 in that unit test. `/health` scrape without a play-ack still shows count 0. `turnwise_playback_unmap_total` stays 0 when `note_chunk` ran. Grafana panel screenshot is skipped; the unit-test scrape is the exhibit, not a 900-call result.

Timeout 800 ms plays cached `cannot_speak` when present. Empty PCM is an error. Stale generation PCM is dropped.

ADR-010: CPU default. GPU present on this host is not a TTS default.

## Known limitations

- Real TTS weights are not pinned. Callers hear silence of known duration (stub) or cached stub PCM.
- Product TTFA P50/P95 remain unmet until phase 9's real-time subset.
- TTS→ASR substitutions on the doctor roster were not scored (both models missing).
- UTMOS was not run.

## License

No TTS weight license to copy. Warmup phrases are invented English clinic templates.
