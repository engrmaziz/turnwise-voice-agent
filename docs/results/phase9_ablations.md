# Phase 9 ablations

Each section is method, n, and result-or-blocked. JSON: `docs/results/phase9_ablations.json` (written by the ablation drivers when run).

## 1. Silence-only versus hybrid endpointing

- Method: `turn_model_enabled` false versus true. Columns: early-cutoff, response-gap.
- n: 0
- Result: **blocked** (`matrix_n_not_900`). Unit endpoint policy remains `tests/test_endpoint_policy.py`.

## 2. Hotword bias on versus off

- Method: biasing on versus off. Columns: entity WER, task success.
- n: 0
- Result: **unsupported**. `asr_backend` is empty/stub and has no bias API (ADR-006).

## 3. NLU trained on clean text versus ASR output

- Method: two student checkpoints. Clean-text training is T5.4.1 `--clean`, slip.
- n: 0
- Result: **blocked** (`clean_text_student_never_trained`). Slot F1 stays unpublished (`golden_incomplete`).

## 4. FSM-first versus model-in-the-loop writer

- Method: `evals/unsafe_llm_writer.py` applies slots without validators. Not importable from `server/`.
- n: 1 (unit double)
- Result: FSM illegal writes **0**. Loop writer illegal writes **1**. The unsafe writer exists to lose.

## 5. Zipformer versus Whisper+LocalAgreement-2

- Method: TTFA and entity WER.
- n: 0
- Result: **blocked** (`missing_asr:import_sherpa,import_whisper`). ADR-006 comparison.

Interview: 900 is virtual. The unsafe writer exists to lose. Yes to a wrong readback is a failed scenario.
