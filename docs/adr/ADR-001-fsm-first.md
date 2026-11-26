# ADR-001: The dialogue FSM owns state

- Status: Accepted
- Date: 2026-11-25

## Context

Turnwise books, reschedules, and cancels clinic appointments, answers FAQs, and escalates urgent callers. A wrong write or a missed urgent symptom is a user-visible failure. Large language models are useful for paraphrase and for mapping odd utterances onto a schema. They are not a reliable place to keep the booking.

## Decision

The dialogue finite-state machine is the only writer of dialogue state.

The model may propose `(intent, slots)` or a paraphrased reply. Validators accept or reject that proposal with the same checks used for the distilled NLU. Grammar-constrained decoding (GBNF or a JSON schema) is required for structured model output. Free text is not parsed with regular expressions to recover an intent.

The model does not:

- transition dialogue state
- do date or time arithmetic
- check availability
- write or cancel a booking
- decide that a call is urgent

Urgent symptoms have a deterministic keyword path. A keyword hit escalates even when a classifier disagrees. Relative dates are resolved from the session clock and timezone, not by the model.

Closed-set entities (doctors, services) resolve against the catalog. Raw ASR text is never written to the database.

## Consequences

- Template replies keep the booking path alive when the model is slow or down.
- Every booking write needs an idempotency key (`session_id` + `turn_id`) and an optimistic lock. Those land with the calendar tool, not in this milestone.
- Paraphrase is capped and optional. The state transition is already decided before the model speaks.
- Evaluation of task success reads the database, not the transcript the model produced.

The table-driven machine in Phase 6 (`dialogue/transitions.toml`, `dialogue/table.py`) is that writer. Calendar writes go through `tools/calendar.py` from `EXECUTE` only. Proposals use the same validators as NLU. Urgent keywords escalate without the classifier.
