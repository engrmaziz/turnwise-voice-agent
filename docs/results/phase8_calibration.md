# Phase 8 calibration

Status: **not collected**.

`training/emotion/call_like.jsonl` contains one object, `{"status":"not_collected"}`. There are not 30 labeled call-like utterances, so there is no table of predicted distressed versus a human label, and there is no ECE.

`evals/emotion/calibrate.py` refuses to invent five reliability bins when that status is set (`tests/test_calibrate_refuses_missing.py`).

Acted-to-call shift remains a limitation even if a future ECE on 30 utterances looks good. Thirty bins of six are noisy; that table would be an honesty artifact, not a clinical study. `emotion_model_enabled` stays false (ADR-011).
