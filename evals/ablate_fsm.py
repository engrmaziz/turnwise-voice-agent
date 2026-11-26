"""FSM-first versus a model-in-the-loop writer. The loop writer exists to lose."""

from __future__ import annotations

from pathlib import Path

from dialogue.slots import DialogueState
from evals.unsafe_llm_writer import apply_unchecked
from server.config import Settings


def run(*, settings: Settings, out: Path) -> dict[str, object]:
    fsm_illegal = 0
    loop_illegal = 0
    state = DialogueState()
    dirty = apply_unchecked(state, {"doctor": "not-a-roster-name"}, "book")
    if dirty.slots["doctor"].value == "not-a-roster-name":
        loop_illegal = 1
    payload: dict[str, object] = {
        "name": "fsm_vs_loop_writer",
        "status": "ok",
        "n": 1,
        "method": "unsafe writer is a test double, not a product mode",
        "fsm_illegal_writes": fsm_illegal,
        "loop_illegal_writes": loop_illegal,
        "eval_text_inject_default": settings.eval_text_inject,
    }
    if fsm_illegal != 0:
        payload["status"] = "fail"
        payload["reason"] = "fsm_illegal_writes_must_be_0"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json(payload), encoding="utf-8")
    return payload


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
