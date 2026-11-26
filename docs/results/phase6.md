# Phase 6 results

Host: Python 3.11.9, Windows-10-10.0.26300-SP0. Numbers below came from running the named command on this machine. No GBNF LLM binary, no task-success percentage, and no FAQ embedding model is claimed here.

## Entry criteria

| Gate | Status |
|---|---|
| M4.1 `TURN_END` | met (Phase 4) |
| M3.5 instants and slot confidence | met (Phase 3) |
| T5.4.3 matcher off default path | met. `regex_slots_enabled` defaults **false**. `server/app.py` does not import `dialogue.regex_slots`. |
| T1.4.3 local LLM | **blocked**. `LlmClient.unavailable` on the call path. Tests use `LlmClient.stub`. No fake GBNF binary. |

## M6.1 Table-driven FSM

`dialogue/transitions.toml` is the source. Guards and actions are named functions, not `eval`. Unknown guard, action, or `next_state` fails at load.

`uv run python -c "from dialogue.diagram import render_mermaid; from pathlib import Path; from dialogue.diagram import normalize; print(normalize(render_mermaid()))"` matches appendix C in `docs/plan/11_appendices.md` after whitespace normalize (`tests/test_fsm_table.py::test_diagram_matches_appendix_c`).

Book path on stub NLU (`tests/test_fsm_book.py::test_book_path_reaches_confirm_without_database`):

`GREET` → `IDENTIFY_PATIENT` → `COLLECT_INTENT` → `COLLECT_SLOTS` → `CONFIRM`

No SQLite on that test.

## M6.2 Confirm and repair

Critical slots under `confirm_explicit_below` 0.8 are explicit. `reason` at 0.5 is not. Yes with empty `played_text` leaves pending. Yes binds `played_slots`, not a silent pending value if they differ. Attempt 2 selects `spell_or_digits`. Attempt 3 selects `handoff_summary` with confirmed slots only.

## M6.3 LLM stub, proposals, FAQ

Non-JSON model output raises `LlmGrammarError` (`tests/test_llm_grammar.py`). A proposal date `"tomorrow"` is rejected; `apply_proposal` returns the same state object. `dialogue/proposal.py` does not import the calendar module.

FAQ: token overlap (ADR-009). `faq_min_score` 0.2 STARTING POINT. Empty retrieval returns the refusal template. `turnwise_faq_ungrounded_total` stays 0. Over-long paraphrase (500 characters) is discarded; spoken text equals the template (cap 180).

## M6.4 SQLite calendar

`BEGIN IMMEDIATE`. Idempotency key `f"{session_id}:{turn_id}"`. Two executes with the same key insert one row. A version bump between offer and confirm returns `conflict` plus alternative `start_iso` values. After yes, the appointment row matches confirmed slots. `test_proposal_does_not_insert` leaves row count 0. Parent-is-file migrate raises `CalendarError`.

## M6.5 Timeouts and filler

`tool_filler_after_ms` 300. `tool_hard_timeout_ms` 1500. `tool_retry_limit` 1.

JSON: `docs/results/phase6_filler.json` written by `tests/test_tool_timeout_filler.py`.

| Field | Value |
|---|---|
| tool_sleep_s | 0.4 |
| tool_filler_after_ms | 300 |
| filler_delta_ms | **306.969** |
| success | true |

A 2 s sleep hits the hard timeout. A second `tool_error` after the retry goes to `HANDOFF`. Same-key retry stays at one appointment row.

## M6.6 Urgent keywords

Hits: `chest pain`, `can't breathe`, `cannot breathe`, `shortness of breath`. Miss: `chest` alone. From `GREET` and from `COLLECT_SLOTS` the keyword reaches `URGENT`. Stub NLU intent `book` on the same utterance still results in `URGENT`. NLU and the LLM are not loaded for that path.

False-escalation rate is Phase 9 (needs scenario labels). Unit tests increment `turnwise_urgent_keyword_total` only.

## Commands run

```
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest
```

All four passed on this host. `regex_slots_enabled` is false in the settings object used by CI.

## Known limitations

- The LLM binary is not on the call path. Paraphrase and grammar-constrained proposals are stubbed.
- SAY events have no TTS stage (Phase 7). Filler sets `payload["filler"]=1` for the later TTFA content histogram.
- Token-overlap FAQ is the deterministic baseline, not a semantic retriever (ADR-009).
- No task-success percentage. That is Phase 9.
- SQLite is opened per call in a worker thread. `database is locked` under load is a Phase 10 trigger.
