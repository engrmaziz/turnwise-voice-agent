# Benchmarks

Generated from the JSON sibling named in this file. Do not hand-edit numbers.

- Host: `Windows-10-10.0.26300-SP0`
- Python: `3.11.9`
- CPUs: 16
- RAM GiB: 63.84
- GPU (`nvidia-smi`): `present` `NVIDIA GeForce RTX 3090, 24576`
- Command: `D:\mak_dev\turnwise-voice-agent\evals\bench\__main__.py`
- JSON: `docs/results/bench/20261125T194836Z.json`
- Warmup 5, samples 20
- Fixture text (public-domain): The north wind and the sun were disputing which was the stronger.
- Fixture audio: windows_sapi:docs/results/bench/fixtures/north_wind.wav

| Name | Status | Version | p50 ms | p95 ms | Reason |
|---|---|---|---|---|---|
| `asr.zipformer.finalize` | blocked |  | blocked | blocked | import_sherpa_onnx |
| `asr.whisper_la2.finalize` | blocked |  | blocked | blocked | import_faster_whisper |
| `asr.whisper_la2.stabilization` | blocked |  | blocked | blocked | import_faster_whisper |
| `llm.ttft.grammar_on` | blocked |  | blocked | blocked | missing_llm_binary |
| `llm.ttft.grammar_off` | blocked |  | blocked | blocked | missing_llm_binary |
| `llm.tokens_per_second.grammar_on` | blocked |  | blocked | blocked | missing_llm_binary |
| `llm.tokens_per_second.grammar_off` | blocked |  | blocked | blocked | missing_llm_binary |
| `tts.first_chunk.cpu` | blocked |  | blocked | blocked | missing_tts:import_piper,import_kokoro |
| `tts.first_chunk.gpu` | blocked |  | blocked | blocked | model_layout_unpinned |

A numeric cell is valid only when Status is `ok`. `blocked` means the binary or weights were missing. `not_present` is reserved for a GPU row when `nvidia-smi` failed.
