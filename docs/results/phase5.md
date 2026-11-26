# Phase 5 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine. No Zipformer, Whisper, LLM teacher, or 500-row golden F1 is claimed here.

## Entry criteria

| Gate | Status |
|---|---|
| ADR-006 ASR backend | **blocked**. T5.2.2 cannot render real ASR. CI uses the stub (`Lang` → `Lan`, else insert `uh`). |
| T1.4.3 local LLM | **blocked**. T5.1.2 wrote 200 **hand_authored** scripts (seed 11). Teacher labeling was skipped. |

MUSAN was not present. Noise for the SNR unit test is generated white noise (`generated_white_noise` in `training/nlu/render_audio.py`). TTS render is mark `bench`.

## M5.1 Synthetic caller corpus

`uv run python -m training.nlu.generate --count 200`

| Field | Value |
|---|---|
| Source | `hand_authored` |
| Seed | 11 |
| Full JSONL | `training/nlu/scripts.jsonl` (gitignored) **200** scripts |
| CI fixture | `training/nlu/fixture_scripts.jsonl` **20** scripts, round-robin by intent |
| Fixture SHA-256 | `b4c5d1d4c92e85b55c682dae05dfade33fa1d11a16b463b8c7c12a1d9e5cf530` |
| Invented patients | `training/nlu/schema.py` `FAKE_PATIENTS` |

Every intent appears at least 10 times in the 200. The fixture covers all eight intents.

## M5.2 Render, recognize, align, teach

SNR: `tests/test_snr.py` mixes a 440 Hz sine with generated white noise at a requested 10 dB. Measured SNR is within 1 dB.

Stub ASR (`training/nlu/recognize.py`): forced substitution `Lang` → `Lan`, otherwise insert `uh` after the first token. BIO is projected with Levenshtein (`training/nlu/align_bio.py`). Insertions are `O`.

Alignment example (insertion, from `tests/test_bio_projection.py::test_insertion_is_o`):

```
clean tokens  book    tuesday
clean tags    O       B-date
asr tokens    book    uh       tuesday
projected     O       O        B-date
```

Phonetic substitution `Lang` → `Lan` keeps `B-doctor`. Unrelated `Lang` → `pizza` is `O` and `align_low`.

Teacher: `tests/test_teacher_grammar.py` drops invalid JSON and unknown slot keys. No teacher labels file exists. `uv run python -m training.nlu.teach` prints `teacher=blocked_llm`. Rows used for the student are stub-ASR projections, not teacher JSON.

## M5.3 Golden set

**`golden_incomplete`**. There is no 500-row `training/nlu/golden.jsonl`.

`training/nlu/golden_fixture.jsonl` has **20** lines with `reviewer=engrmaziz` so CI can schema-check. That reviewer field is filled by `golden_sample.py`. It is not a human listen of 20 waveforms. Slot F1 is **not published**.

`evals/nlu/score.py` refuses a file without `reviewer` (`tests/test_score_requires_reviewer.py`).

Identity ceiling on the 20-row fixture (`uv run python -m evals.nlu.score`):

JSON: `docs/results/phase5_score.json`

| Field | Value |
|---|---|
| n | 20 |
| identity_intent_accuracy | 1.0 |
| identity_slot_f1 | 1.0 |
| note | identity ceiling only; unpublished |

Those identity numbers are the scorer agreeing with itself. They are not student slot F1 and not teacher-agreement.

## M5.4 Joint student

Encoder: **`from_scratch`**. Hashed character n-grams plus two linear heads (intent, BIO). Not a transformer. Plan T5.4.1 STARTING POINT was lr `3e-5` (encoder-scale). This trainer uses `TRAIN_LR=0.1`. JSON: `docs/results/phase5_train.json`.

| Field | Value |
|---|---|
| Rows | 200 stub-ASR projections |
| Training-set intent accuracy | **1.0000** |
| Training data SHA-256 | `857dd20c82fe1d7954f7281dd8854f1c5c5ecb52e89e77f70a74f3a0a4b487c6` |
| Export | ONNX + INT8 (`onnxruntime.quantization.quantize_dynamic`) |
| INT8 size | **0.0081 MB** (`docs/results/phase5_student_card.json`) |

Training-set accuracy 1.0 is on 200 synthetic stub transcripts. It is not golden slot F1.

Teacher versus student on the golden ASR column:

| Side | Status |
|---|---|
| Teacher | **blocked** (LLM bench) |
| Student slot F1 | **unpublished** (`golden_incomplete`) |
| Student CPU p50 | **0.3993 ms** (TARGET 30 ms, met) |
| Student CPU p95 | 0.5471 ms |
| INT8 size | 0.0081 MB |

CPU latency from `uv run python -m evals.bench.nlu_latency` (warmup 5, samples 20, `time.perf_counter`) on `models/weights/nlu_intent.onnx` + `nlu_bio.onnx`. JSON: `docs/results/phase5_nlu_latency.json`. ADR-008 was **not** opened.

`nlu_model_path` default is empty. Missing weights load `NluScorer.unavailable` and the stage emits `nlu_ok=0`. `dialogue/regex_slots.py` exists for ablation T9.5.4 and is **not** imported by `server/app.py`.

The NLU stage reads `FINAL.spoken`, never `normalized`. Doctor spans are roster lines (`tests/test_nlu_stage.py::test_doctor_slot_is_catalog_id`). Timeout 40 ms → `nlu_ok=0` with no regex fallback.

## M5.5 Disfluency and phonetic resolve

`tests/test_disfluency.py`: "Tuesday no Wednesday" keeps Wednesday. "Tuesday no, the morning" keeps Tuesday.

`tests/test_phonetic.py`: `Dr.` is stripped. Two catalog rows that share a last name (`Dr. Ann Khan`, `Dr. Bob Khan`) return no id and both candidates. Heard `Khan` versus `Dr. Khan` / `Dr. Kahn` is **not** a tie under this formula (1.0 vs 0.76). `Lang` against the roster resolves to `Dr. Avery Lang`.

Score: `0.6 * JaroWinkler(metaphone) + 0.4 * JaroWinkler` after title strip. Starting thresholds `phonetic_min_score=0.82`, `phonetic_margin=0.05`. Sweep: **untuned** (`docs/results/phase5_phonetic.md`) because golden is incomplete. Settings were not changed.

## Not run / blocked

| Row | Status |
|---|---|
| Real TTS render | bench / blocked (no TTS worker) |
| MUSAN mix | not present; generated white noise used in the SNR test |
| Zipformer / Whisper ASR transcripts | blocked (ADR-006) |
| LLM teacher labels | blocked (LLM bench) |
| 500-row human golden | `golden_incomplete` |
| Published slot F1 | unpublished |
| Phonetic sweep grid | `untuned` |
| Hardware tier | blocked (ADR-004) |
| Week-6 SQLite book path | not this phase (phase 6) |
