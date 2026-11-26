# Phase 8 results

Host: not a training run. No acted-emotion confusion matrix is published. No ECE. `emotion_model_enabled` defaults false (ADR-011).

## Entry criteria

| Gate | Status |
|---|---|
| M6.6 keyword tests | met (`tests/test_urgent_keyword.py`, re-run from `tests/test_frustration_policy.py`) |
| M4.2 ONNX pool pattern | met (`models/emotion_pool.py` mirrors timeout + generation drop) |
| T8.1.1 licenses | met. CREMA-D ODbL 1.0 + DbCL 1.0. RAVDESS CC BY-NC-SA 4.0, script exit 2 without `--research-nc`. |

## M8.1 Utterance emotion

| Item | Value |
|---|---|
| Mapping | HAP/NEU/01/02/03 → calm. ANG/DIS/05/07 → frustrated. FEA/SAD/04/06 → distressed. RAVDESS 08 dropped. |
| Train | `skipped` (`training/emotion/train.py` writes `train_status.json` when wavs or libs are missing). T8.1.3 is slip. |
| Export | `skipped` (no checkpoint). Stub always returns `None`. |
| Timeout | `tests/test_emotion_timeout.py`. Timeout increments `turnwise_emotion_timeouts_total` and leaves `last_emotion` unset. |

No acted macro-F1 is a product number.

## M8.2 Fusion

Starting weights: `0.4, 0.2, 0.2, 0.1, 0.1`. Startup refuses a sum other than 1.0.

| Case | Score |
|---|---|
| audio `None`, text missing (0.5), 3 repairs, 2 nos, no barge | **0.4** |
| audio `None`, text 0.0, 3 repairs, 2 nos, barge | **0.6** |
| calm audio 1.0, text 1.0, zero repairs | **0.0** |

The plan's demo line "three repairs and two nos still exceed 0.65" is **false** under these weights. Dialogue terms max out at 0.6. Tests lock 0.4 / 0.6 to 1e-6 rather than fudge weights. A timeout is identical to `None`.

Lexicon: "please" / "thank you" raise calm; "stupid" / "useless" lower it. `sentiment_model_enabled` defaults false. No cloud API.

## M8.3 Policy

One over-threshold turn does not offer. Two consecutive turns do. A below-threshold turn resets the count. `offer_human` is not `HANDOFF`. Yes on the offer template is `offer_human_yes` → `HANDOFF`. Keyword plus a high score is still `URGENT`. Short templates exist for `ask_slot` and `confirm`. `tts_frustrated_speed` 0.9 applies when `session.offer_human` is true; digit mode still wins.

On the default stub path the fusion score cannot cross 0.65, so the two-turn latch does not fire from audio. `speak_to_human` still hands off in one turn.

## M8.4 Calibration

`training/emotion/call_like.jsonl` is `{"status":"not_collected"}`. `evals/emotion/calibrate.py` exits 2 and does not invent bins. See `docs/results/phase8_calibration.md`.

## Limitation

Acted-emotion corpora transfer poorly to clinic calls. A confusion matrix on CREMA-D or RAVDESS would not be a production quality number even if one existed. Thirty operator-labeled utterances would not be a clinical study. The audio model stays off until this file and ADR-011 say otherwise. Keywords own safety; emotion owns courtesy.

## Metrics

`turnwise_emotion_seconds`, `turnwise_emotion_timeouts_total`, `turnwise_fusion_score`, `turnwise_offer_human_total`.
