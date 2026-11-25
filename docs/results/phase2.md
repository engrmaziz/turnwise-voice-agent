# Phase 2 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine.

## Resample (T2.1.1)

`resample_mono_pcm16` on a 20 ms 48 kHz 440 Hz sine to 16 kHz. Warmup 5, then 50 samples. Clock: `time.perf_counter`.

| Metric | Value |
|---|---|
| p50 | **0.1446 ms** |
| Allocation |  not a budget line of its own; ingress frame allocation is 20 ms |

## VAD ONNX (T2.3.1)

`python scripts/download_silero_vad.py` wrote `models/weights/silero_vad.onnx` (2 204 103 bytes). Git ignores `*.onnx`. License: Silero VAD, fetched from the upstream GitHub raw URL, not redistributed in git.

| Field | Value |
|---|---|
| File | `silero_vad.onnx` |
| Opset | not exposed by `onnxruntime.InferenceSession`; recorded as unknown rather than guessed |
| Window | 512 samples at 16 kHz (settings `vad_window_samples`) |
| Inference p50 | **0.5195 ms** (20 calls after 3 warmup, executor path, zeros window) |
| Allocation | 10 ms |

## Pre-roll (T2.3.3)

Speech-start snapshot on a 25-frame ring plus the triggering frame is 16 640 bytes (26 × 640). Underrun at 100 ms is covered by `tests/test_preroll.py`.

## Noise versus speech (T2.3.4)

Fixture license: **generated-white-noise** (not MUSAN). RMS-scaled stub probabilities, same hysteresis as production.

| Fixture | Speech starts |
|---|---|
| 500 ms silence then 800 ms 440 Hz at amplitude 0.25 | 1 |
| 1.3 s white noise at amplitude 0.008 | 0 |

False starts on this noise file do not exceed speech starts. `vad_speech_threshold` 0.5 stays STARTING POINT. No ADR-005.

## AEC / speakers (T2.2.3)

Server-side AEC is a non-goal. `session.barge_in_enabled` is the hello `aec` boolean from `track.getSettings()`, not the constraint the client asked for. `Session.request_barge_in` is a no-op when the flag is false. If `client/prompts/headphones.pcm` is missing, the server logs `prompt_missing` and continues without barge-in.

| Browser | Speakers vs headphones | `getSettings().echoCancellation` | Barge-in armed | Result |
|---|---|---|---|---|
| | | | | not run |

## Audio quality (M2.4)

`tests/test_audio_quality.py`: 2.9 s of zeros does not fire; 3.0 s emits `SESSION_END` once with `reason=audio_dead`. A sine does not move `turnwise_audio_dead`. Clip fraction 2% at peak 32767 crosses `audio_clip_fraction` 0.01.

## PCM on the bus

PCM bytes live on `Session.put_pcm` / `get_pcm`, keyed by `frame_index`. `Event.payload` stays scalars (`samples=320`). Payload is never a hex dump of audio.
