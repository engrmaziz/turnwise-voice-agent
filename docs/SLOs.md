# Service level objectives

Every row is a target. None of these have been measured on a call. The only latency number this repo has actually run is the in-process stage hop in `docs/ARCHITECTURE.md`.

`turnwise_ttfa_seconds` and `turnwise_ttfa_content_seconds` observe on the client's play-ack (`tests/test_ttfa_observe.py`). A `/metrics` scrape with no play-ack still has count 0. Product P50/P95 remain unmet.

## Gates

| Metric | Target | Definition |
|---|---|---|
| Time to first audio, P50 | ≤ 700 ms | End of user speech (VAD) until the client acks playback of the first audio frame. Filler counts. Localhost until a transport benchmark says otherwise. |
| Time to first audio, P95 | ≤ 1200 ms | Same clock as P50. |
| Task success, clean audio | ≥ 90% | The database matches the scenario: the right appointment was booked, moved, or cancelled. A judge model does not decide this. |
| Task success, 10 dB SNR | ≥ 75% | Same check, with noise mixed at 10 dB SNR. |
| False barge-in | < 2% of agent utterances | An agent utterance was cancelled when the caller did not take the turn. Backchannels during agent speech are not barge-ins. "Okay" as the answer to a yes/no question is a real turn. |
| Early cutoff | < 5% of user turns | The agent started a reply before the caller had finished the turn the scenario required. |
| Slot F1 on ASR output | Report only | Intent/slot scores on recognizer text, not on the clean script. Phase 5 is `golden_incomplete`; no numeric gate until 500 reviewed rows exist (`docs/results/phase5.md`). |
| Urgent-case recall | ~100% | Scenarios marked urgent that reached the escalation path. The keyword list alone must be sufficient; a classifier miss does not block escalation. |
| Critical-slot error after confirmation | ~0% | The confirmed value equals the scenario's value. The caller saying yes to a wrong readback is a failure. Low-confidence names and numbers are read back spelled or digit by digit, and yes binds the value that was actually played. |

## Recorded, no numeric target yet

| Metric | Definition |
|---|---|
| Time to first content audio | Same clock as time to first audio, ignoring frames whose phrase is in the filler set. Stops a filler from satisfying the 700 ms target on a turn that then goes quiet. |
| False urgent escalation | Share of scenarios marked non-urgent that still escalated. The keyword path will fire on past-tense or negated symptoms ("I had chest pain last year"). Over-trigger is accepted; hiding the rate is not. |

## How a number becomes real

A gate is met only when the eval harness (roadmap phase 10) reports it from audio, or when a latency histogram in this process recorded the samples. Until then the status of every gate is unmet.
