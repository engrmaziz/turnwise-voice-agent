# Benchmarks

Generated from the JSON sibling named in this file. Do not hand-edit numbers.

- Host: `Windows-10-10.0.26300-SP0`
- Python: `3.11.9`
- CPUs: 16
- RAM GiB: 63.84
- GPU (`nvidia-smi`): `present` `NVIDIA GeForce RTX 3090, 24576`
- Command: `D:\mak_dev\turnwise-voice-agent\evals\bench\__main__.py`
- JSON: `docs/results/bench/20261126T200406Z.json`
- Warmup 5, samples 20
- Fixture text (public-domain): The north wind and the sun were disputing which was the stronger.
- Fixture audio: windows_sapi:docs/results/bench/fixtures/north_wind.wav
- Whisper LA-2 rows: `docs/results/phase3_whisper.json` (2026-11-27, faster-whisper 1.2.1 tiny.en). Not from the suite JSON above.

| Name | Status | Version | p50 ms | p95 ms | Reason |
|---|---|---|---|---|---|
| `asr.zipformer.finalize` | ok | 2.0.3;zipformer2;int8;en-2023-06-26 | 32.4 | 37.5 |  |
| `asr.whisper_la2.finalize` | ok | 1.2.1;faster-whisper;tiny.en;cpu-int8 | 490.8 | 529.8 | north-wind `docs/results/phase3_whisper.json` |
| `asr.whisper_la2.stabilization` | ok | 1.2.1;faster-whisper;tiny.en;la2 | 476.8 | 476.8 | last-window transcribe; n=1 delay |
| `llm.ttft.grammar_on` | ok | ollama:qwen3.5:4b | 57.2 | 69.5 |  |
| `llm.ttft.grammar_off` | ok | ollama:qwen3.5:4b | 60.7 | 105.0 |  |
| `llm.tokens_per_second.grammar_on` | ok | ollama:qwen3.5:4b | 87.0 tok/s | 91.7 tok/s |  |
| `llm.tokens_per_second.grammar_off` | ok | ollama:qwen3.5:4b | 128.8 tok/s | 130.0 tok/s |  |
| `tts.first_chunk.cpu` | ok | piper-tts:1.8.0;voice=en_US-amy-low;device=cpu | 34.5 | 36.4 |  |
| `tts.first_chunk.gpu` | blocked |  | blocked | blocked | model_layout_unpinned |

A numeric cell is valid only when Status is `ok`. `blocked` means the binary or weights were missing. `not_present` is reserved for a GPU row when `nvidia-smi` failed.
