# ADR-011: Emotion model default-off

- Status: Accepted
- Date: 2026-11-26

## Context

Phase 8 adds an utterance-level 3-class audio score (calm / frustrated / distressed) and a late-fusion policy that can *offer* a human. Acted corpora (CREMA-D, RAVDESS) are a training convenience, not clinic-call audio. Thirty call-like labels were not collected (`training/emotion/call_like.jsonl` is `{"status":"not_collected"}`). `evals/emotion/calibrate.py` refuses to invent ECE bins.

T6.6.1's keyword path still escalates with this classifier unloaded. Emotion must not own urgency, write bookings, or skip keywords.

## Decision

`TURNWISE_EMOTION_MODEL_ENABLED` defaults **false**. The process loads `EmotionScorer.stub`, which always returns `None` to fusion. Dialogue terms (repairs, repeated confirm-no, barge-in, lexicon sentiment) still run.

The flag flips in this ADR, not by a silent env change in production, and only after:

1. `evals/emotion/calibrate.py` writes an ECE table from 30 labeled call-like utterances, and
2. the limitation paragraph in `docs/results/phase8.md` still names acted-to-call shift.

RAVDESS is CC BY-NC-SA 4.0. Product use of that corpus needs a paid license. CREMA-D is ODbL 1.0 + DbCL 1.0.

## Consequences

- Starting fusion weights cannot reach `frustration_threshold` 0.65 without an audio term (dialogue terms max out at 0.6). A courtesy offer from fusion therefore does not fire on the default stub path. `speak_to_human` and the repair ladder still hand off.
- Timeouts (`emotion_timeout_ms` 80) are identical to missing audio.
- A future enable is a new commit that changes this ADR's Decision to true and points at a real calibration file.
