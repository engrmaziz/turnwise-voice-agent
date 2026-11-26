# Generation cancellation is the barge-in bus

NLU-on-ASR ablation numbers are blocked (`docs/results/phase9.md`: `nlu` status `blocked`, n=0). Endpointing ablation is also blocked. The technical result we can quote is already in `docs/ARCHITECTURE.md`: the stage hop that every barge-in has to beat.

## What the bus does

Every event is stamped with `(session_id, turn_id, generation)`. `Session.barge_in` increments generation and turn, then cancels speaking tasks. Stages drop events whose generation no longer matches. There is no await between the increment and the cancels. ADR-002.

That is the interrupt path. TTS does not "finish the sentence." Audio-out sees a new generation and stops packing frames. ASR hypotheses submitted under the old generation are discarded.

## Measured hop

Sequential `emit` of one event into a stage whose handler returns immediately. Twenty warmup iterations, then 200 samples. Clock starts immediately before `emit` and stops when the handler begins. This is the bus, not a model.

Three consecutive runs of `tests/test_stage_overhead.py` on Python 3.11.9, Windows 10.0.26300, reported medians of **0.0825 ms**, **0.0806 ms**, and **0.0734 ms** (`docs/ARCHITECTURE.md`). The test fails if a run's median reaches 5 ms.

A cancel that waited on a model worker would miss the 250 ms barge-in speech floor. The hop numbers say the queue and drop are not that wait.

## What this is not

It is not a TTFA P50. Product TTFA is unmet; the realtime subset is `skipped` (`docs/results/phase9.md`). Load p95 is empty because the scripted caller does not play-ack (`docs/results/phase10_load.md`). It is not an NLU-on-ASR F1. Those JSON keys are `blocked`.
