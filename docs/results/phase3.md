# Phase 3 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine. Do not hand-edit.

## ASR backends (M3.2)

JSON: `docs/results/phase3_asr_compare.json` from `python -m evals.bench.phase3`. Twenty Piper-spoken fixtures through CPU Zipformer (sherpa-onnx 2.0.3, zipformer2 int8 en-2023-06-26). Whisper+LA-2 stayed `weights_unpinned`. Stabilization delay uses `delay_basis=utterance_end` (post-audio drain, not a paper number).

| Backend | Finalize p50 / p95 | Stabilization delay p50 | Delay basis |
|---|---|---|---|
| zipformer | 173.7 ms / 213.0 ms | 173.7 ms | utterance_end |
| whisper_la2 | blocked (`weights_unpinned`) | blocked | utterance_end |

North-wind post-stream drain (different JSON, long SAPI wav already accepted before the clock): `docs/results/bench/20261126T192516Z.json` row `asr.zipformer.finalize` p50 **62.1 ms** / p95 **67.3 ms**. That row is not the ADR-006 pick.

ADR-006: **Accepted**, backend **zipformer**. Compare finalize p50 **173.7 ms** misses the 100 ms TARGET. Default `TURNWISE_ASR_BACKEND` stays empty so CI is weight-free. Operators set `zipformer` after `uv sync --extra asr` and `python scripts/download_models.py`. ADR-003 stays Proposed (LLM TTFT still missing).

## Entity WER (M3.3)

JSON: `docs/results/phase3_entity_wer.json`. Roster: 15 invented names in `data/doctors.txt`. The 30-name set is that roster doubled and truncated. Piper spoke `see doctor <surname tokens>`. Hits require every name token (minus `Dr.`) in the hypothesis.

| Bias | Entity error rate | Status |
|---|---|---|
| off | 0.833 (25/30 misses) | ok |
| on |  | unsupported (greedy Zipformer has no hotword API) |

CSV: `docs/results/phase3_entity_wer.csv`, `docs/results/phase3_stab.csv`.

## ITN (M3.4)

Interpreter: CPython 3.11.9 on Windows. `nemo_text_processing` import: **ModuleNotFoundError**. Rule fallback is the Windows default.

`apply_rules("march third at two thirty")` → `March 3 at 2:30`. Spoken payload on finals stays the recognizer string. Partials have `spoken` and no `normalized`.

ITN sync p50 (50 samples after 5 warmup, `time.perf_counter`): **0.0459 ms**.

## Temporal + slot confidence (M3.5)

`tests/test_relative_dates.py`: Tuesday 2026-03-03, "next Tuesday" is 2026-03-10 in `America/New_York`. "day after tomorrow" from 2026-03-07 18:00 is two local midnights (2026-03-09 00:00 EDT), not +48 h UTC. "sometime" is unresolved.

Slot confidence: span covering 0.9 and 0.4 yields 0.4. Empty span and missing word scores yield 0.0.

Temporal p50 for `"next Tuesday"`: **0.0078 ms**. ITN + temporal sum p50: **0.0537 ms** (allocation 10 ms).
