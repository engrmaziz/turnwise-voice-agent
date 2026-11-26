"""Three low-confidence turns hand off with the asr collapse template."""

from pathlib import Path

from prometheus_client import CollectorRegistry

from evals.harness import default_eval_settings
from models.llm_client import LlmClient
from pipeline.event import EventKind
from pipeline.metrics import build_stage_metrics
from pipeline.session import Session
from pipeline.stages.dialogue import DialogueHandler
from tests.support import counter_value


async def test_three_low_confidence_turns_handoff(tmp_path: Path) -> None:
    settings = default_eval_settings()
    session = Session("asr-collapse")
    metrics = build_stage_metrics(CollectorRegistry())
    handler = DialogueHandler(
        session=session,
        settings=settings,
        metrics=metrics,
        llm=LlmClient.unavailable(timeout_ms=50),
        db_path=tmp_path / "clinic.sqlite",
    )
    await handler.start()
    for _ in range(3):
        event = session.create_event(
            EventKind.NLU,
            {
                "spoken": "um",
                "intent": "book",
                "slots": "{}",
                "nlu_ok": 1,
                "slot_conf": 0.2,
            },
        )
        await handler(event)
    assert handler.machine.state.state_id == "HANDOFF"
    assert handler.machine.state.last_template == "handoff_asr"
    assert counter_value(metrics.degraded, rung="asr") >= 1.0
