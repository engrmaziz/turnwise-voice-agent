# Phase 3 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine.

## ASR backends (M3.2)

JSON: `docs/results/phase3_asr_compare.json`. Twenty text fixtures. Weights are not pinned, so both backends are `blocked`. Stabilization delay is recorded as `utterance_end` with null p50/p95 rather than a copied paper number.

| Backend | Finalize | Stabilization delay p50 | Delay basis |
|---|---|---|---|
| zipformer | blocked | blocked | utterance_end |
| whisper_la2 | blocked | blocked | utterance_end |

ADR-006: **blocked**. `TURNWISE_ASR_BACKEND` stays empty. The call path uses the stub recognizer. ADR-003 stays Proposed.

## Entity WER (M3.3)

JSON: `docs/results/phase3_entity_wer.json`. Roster: 15 invented names in `data/doctors.txt`. The 30-name set is that roster doubled and truncated. TTS command is empty, so both rows are `blocked` (`tts_blocked`). Text-only WER is not entity WER.

| Bias | Entity WER |
|---|---|
| off | blocked |
| on | blocked |

CSV stand-in (matplotlib not used): `docs/results/phase3_entity_wer.csv`, `docs/results/phase3_stab.csv`.

## ITN (M3.4)

Interpreter: CPython 3.11.9 on Windows. `nemo_text_processing` import: **ModuleNotFoundError**. Rule fallback is the Windows default.

`apply_rules("march third at two thirty")` → `March 3 at 2:30`. Spoken payload on finals stays the recognizer string. Partials have `spoken` and no `normalized`.

ITN sync p50 (50 samples after 5 warmup, `time.perf_counter`): **0.0459 ms**.

## Temporal + slot confidence (M3.5)

`tests/test_relative_dates.py`: Tuesday 2026-03-03, "next Tuesday" is 2026-03-10 in `America/New_York`. "day after tomorrow" from 2026-03-07 18:00 is two local midnights (2026-03-09 00:00 EDT), not +48 h UTC. "sometime" is unresolved.

Slot confidence: span covering 0.9 and 0.4 yields 0.4. Empty span and missing word scores yield 0.0.

Temporal p50 for `"next Tuesday"`: **0.0078 ms**. ITN + temporal sum p50: **0.0537 ms** (allocation 10 ms).
