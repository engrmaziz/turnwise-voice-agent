"""Paraphrase that drops a catalog name is discarded. The template is spoken."""

from prometheus_client import CollectorRegistry

from dialogue.planner import speak
from dialogue.slots import SlotValue
from models.llm_client import LlmClient
from pipeline.metrics import build_stage_metrics
from server.config import Settings
from tests.support import counter_value


async def test_paraphrase_dropping_doctor_keeps_template() -> None:
    template = "I will book Doctor Khan on November twenty-sixth at two thirty p.m."
    llm = LlmClient.stub(timeout_ms=2000, response='{"text": "the cardiologist can see you"}')
    metrics = build_stage_metrics(CollectorRegistry())
    spoken = await speak(
        "confirm_readback",
        fallback=template,
        settings=Settings(),
        llm=llm,
        paraphrase=True,
        slots={"doctor": SlotValue(value="Dr. Khan", status="confirmed", confidence=1.0)},
        metrics=metrics,
    )
    assert spoken == template
    assert counter_value(metrics.planner_paraphrase_discard, reason="missing_slot") == 1.0


async def test_paraphrase_keeping_doctor_is_used() -> None:
    template = "I will book Doctor Khan at two thirty p.m."
    llm = LlmClient.stub(
        timeout_ms=2000,
        response='{"text": "Doctor Khan is free at two thirty p.m."}',
    )
    spoken = await speak(
        "confirm_readback",
        fallback=template,
        settings=Settings(),
        llm=llm,
        paraphrase=True,
        slots={
            "doctor": SlotValue(value="Dr. Khan", status="confirmed"),
            "time": SlotValue(value="14:30", status="confirmed"),
        },
    )
    assert spoken == "Doctor Khan is free at two thirty p.m."
