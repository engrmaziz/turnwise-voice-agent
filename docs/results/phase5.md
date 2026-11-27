# Phase 5 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine.

## Entry criteria

| Gate | Status |
|---|---|
| ADR-006 ASR backend | **Accepted zipformer**. T5.2.2 rendered 700 Piper clips through CPU Zipformer (`--backend zipformer --hotwords`). CI still uses the stub (`Lang` → `Lan`, else insert `uh`). |
| T1.4.3 local LLM | **blocked**. Scripts are **hand_authored** (seed 11). Teacher labeling was skipped. |

MUSAN was not present. Noise for the SNR unit test is generated white noise (`generated_white_noise` in `training/nlu/render_audio.py`).

## M5.1 Synthetic caller corpus

`uv run python -m training.nlu.generate --count 700 --out training/nlu/scripts.jsonl --skip-fixture`

| Field | Value |
|---|---|
| Source | `hand_authored` |
| Seed | 11 |
| Full JSONL | `training/nlu/scripts.jsonl` (gitignored) **700** scripts |
| CI fixture | `training/nlu/fixture_scripts.jsonl` **20** scripts, round-robin by intent (unchanged) |
| Fixture SHA-256 | `b4c5d1d4c92e85b55c682dae05dfade33fa1d11a16b463b8c7c12a1d9e5cf530` |
| Invented patients | `training/nlu/schema.py` `FAKE_PATIENTS` |

The fixture covers all eight intents. `--skip-fixture` keeps the committed 20-line SHA stable.

## M5.2 Render, recognize, align, teach

SNR: `tests/test_snr.py` mixes a 440 Hz sine with generated white noise at a requested 10 dB. Measured SNR is within 1 dB.

CI stub ASR (`training/nlu/recognize.py` default): forced substitution `Lang` → `Lan`, otherwise insert `uh` after the first token.

Host run: Piper `en_US-amy-low` then Zipformer2 int8 `en-2023-06-26` with roster hotwords (`hotword_score=2.0`). Command: `uv run python -m training.nlu.recognize --scripts training/nlu/scripts.jsonl --out training/nlu/asr_rows.jsonl --backend zipformer --hotwords`. **700** rows, **0** empty `asr_text`, **422** `align_low`. BIO is projected with Levenshtein (`training/nlu/align_bio.py`). Insertions are `O`.

Alignment example (insertion, from `tests/test_bio_projection.py::test_insertion_is_o`):

```
clean tokens  book    tuesday
clean tags    O       B-date
asr tokens    book    uh       tuesday
projected     O       O        B-date
```

Phonetic substitution `Lang` → `Lan` keeps `B-doctor`. Unrelated `Lang` → `pizza` is `O` and `align_low`.

Teacher: `tests/test_teacher_grammar.py` drops invalid JSON and unknown slot keys. No teacher labels file exists. `uv run python -m training.nlu.teach` prints `teacher=blocked_llm`. The student trains on Zipformer ASR projections, not teacher JSON.

## M5.3 Golden set

`training/nlu/golden.jsonl` has **500** rows (gitignored). Reviewer is `bio_projection`: BIO was projected from the script onto Zipformer ASR and schema-validated. **`waveform_listen=false`**. This is not 500 human listens of waveforms. `align_low` on the golden slice: **302 / 500**.

Intent counts: book 91, reschedule 66, cancel 69, check_appointment 66, faq 56, speak_to_human 67, urgent_symptom 49, out_of_scope 36.

Hold-out: `training/nlu/golden_sample.py --size 500 --reviewer bio_projection --train-out training/nlu/asr_train.jsonl` (200 train / 500 golden, stratified).

`training/nlu/golden_fixture.jsonl` has **20** lines with `reviewer=engrmaziz` so CI can schema-check. That reviewer field is filled by `golden_sample.py`. It is not a human listen of 20 waveforms.

`evals/nlu/score.py` refuses a file without `reviewer` (`tests/test_score_requires_reviewer.py`).

JSON: `docs/results/phase5_score.json`

| Field | Value |
|---|---|
| n | 500 |
| reviewers | `bio_projection` |
| waveform_listen | false |
| identity_intent_accuracy | 1.0 |
| identity_slot_f1 | 1.0 |
| student_intent_accuracy | **0.998** |
| student_slot_f1 | **0.7173** |
| note | student scores on 500 Zipformer-ASR rows with BIO projection; not a waveform listen |

Identity numbers are the scorer agreeing with itself. Student F1 is on the Zipformer ASR column versus projected BIO. It is not teacher-agreement and not a waveform-listen SLO.

## M5.4 Joint student

Encoder: **`from_scratch`**. Hashed character n-grams plus two linear heads (intent, BIO). Not a transformer. Plan T5.4.1 STARTING POINT was lr `3e-5` (encoder-scale). This trainer uses `TRAIN_LR=0.1`. JSON: `docs/results/phase5_train.json`.

| Field | Value |
|---|---|
| Rows | 200 Zipformer-ASR hold-in (`training/nlu/asr_train.jsonl`) |
| Training-set intent accuracy | **1.0000** |
| Training data SHA-256 | `45cde55fe6cb2e902c9da9f999775fef41e460c91ac0f517dc5646799ab62866` |
| Export | ONNX + INT8 (`onnxruntime.quantization.quantize_dynamic`) |
| INT8 size | **0.0081 MB** (`docs/results/phase5_student_card.json`) |

Training-set accuracy 1.0 is on 200 Zipformer transcripts that are not in the golden 500.

Teacher versus student on the golden ASR column:

| Side | Status |
|---|---|
| Teacher | **blocked** (LLM bench) |
| Student intent accuracy | **0.998** (500 projection-reviewed Zipformer rows) |
| Student slot F1 | **0.7173** (same rows; not a waveform listen) |
| Student CPU p50 | **0.5568 ms** (TARGET 30 ms, met) |
| Student CPU p95 | 0.7729 ms |
| INT8 size | 0.0081 MB |

CPU latency from `uv run python -m evals.bench.nlu_latency` (warmup 5, samples 20, `time.perf_counter`) on `models/weights/nlu_intent.onnx` + `nlu_bio.onnx`. JSON: `docs/results/phase5_nlu_latency.json`. ADR-008 was **not** opened.

`nlu_model_path` default is empty. Missing weights load `NluScorer.unavailable` and the stage emits `nlu_ok=0`. `dialogue/regex_slots.py` exists for ablation T9.5.4 and is **not** imported by `server/app.py`.

The NLU stage reads `FINAL.spoken`, never `normalized`. Doctor spans are roster lines (`tests/test_nlu_stage.py::test_doctor_slot_is_catalog_id`). Timeout 40 ms → `nlu_ok=0` with no regex fallback.

## M5.5 Disfluency and phonetic resolve

`tests/test_disfluency.py`: "Tuesday no Wednesday" keeps Wednesday. "Tuesday no, the morning" keeps Tuesday.

`tests/test_phonetic.py`: `Dr.` is stripped. Two catalog rows that share a last name (`Dr. Ann Khan`, `Dr. Bob Khan`) return no id and both candidates. Heard `Khan` versus `Dr. Khan` / `Dr. Kahn` is **not** a tie under this formula (1.0 vs 0.76). `Lang` against the roster resolves to `Dr. Avery Lang`.

Score: `0.6 * JaroWinkler(metaphone) + 0.4 * JaroWinkler` after title strip. Sweep on 500 golden rows, catalog `data/doctors.txt`, scoring **correct** catalog ids (not merely emitting an id): `docs/results/phase5_phonetic.md`. Winner **0.75 / 0.03** (50 correct / 51 resolved / 55 eligible) beat the starting point 0.82 / 0.05 (46 / 46 / 55). Production `phonetic_min_score=0.75`, `phonetic_margin=0.03`.

## Not run / blocked

| Row | Status |
|---|---|
| MUSAN mix | not present; generated white noise used in the SNR test |
| LLM teacher labels | blocked (LLM bench) |
| 500-row waveform listen | not done; reviewer is `bio_projection` |
| Waveform-listen slot F1 SLO | unpublished (`waveform_listen=false`) |
| Hardware tier | blocked (ADR-004 Proposed) |
