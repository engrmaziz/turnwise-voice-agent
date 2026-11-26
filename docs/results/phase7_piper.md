# Phase 7 Piper CPU first-chunk

Host: Python 3.11.9, Windows-10-10.0.26300-SP0, 16 CPUs, 63.84 GiB RAM. Numbers came from `python -m evals.bench` on this machine. Do not hand-edit.

JSON: `docs/results/bench/20261126T175404Z.json`  
Markdown: `docs/benchmarks.md`  
ADR: `docs/adr/ADR-010-tts-device.md`

| Field | Value |
|---|---|
| status | ok |
| version | piper-tts:1.8.0;voice=en_US-amy-low;device=cpu |
| text | Hello this is Turnwise. |
| output_hz | 16000 |
| warmup | 5 |
| samples | 20 |
| p50_ms | 33.93310000683414 |
| p95_ms | 39.1231150002568 |
| TARGET first-chunk p50 | 200 ms |
| miss | no |

GPU first-chunk stayed `blocked` (`model_layout_unpinned`). ASR and LLM rows in the same JSON stayed `blocked`. ADR-004 remains blocked.

Default `tts_backend` is still empty (silence stub). Enabling Piper is `TURNWISE_TTS_BACKEND=piper` after `uv sync --extra tts` and `python scripts/download_models.py`.
