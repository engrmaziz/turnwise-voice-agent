"""ASR stage emits spoken partials and one ITN'd final. No LLM import."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from models.asr_pool import AsrPool
from pipeline.event import Event, EventKind
from pipeline.stages.asr import AsrHandler
from tests.conftest import Harness
from tests.support import counter_value

_PCM = b"\x00\x00" * 320


async def test_partial_is_prefix_of_final_spoken(harness: Harness) -> None:
    pool = AsrPool.stub(harness.settings, harness.metrics)
    seen: list[Event] = []

    async def forward(event: Event) -> None:
        seen.append(event)

    handler = AsrHandler(
        session=harness.session,
        settings=harness.settings,
        engine=pool,
        metrics=harness.metrics,
        forward=forward,
    )
    for index in range(12):
        harness.session.put_pcm(index, _PCM)
        await handler(
            harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        )
    await handler(harness.session.create_event(EventKind.TURN_END, {"reason": "vad_hang"}))
    pool.close()
    partials = [event for event in seen if event.kind is EventKind.PARTIAL]
    finals = [event for event in seen if event.kind is EventKind.FINAL]
    assert partials
    assert len(finals) == 1
    spoken_final = str(finals[0].payload["spoken"])
    for event in partials:
        spoken = str(event.payload["spoken"])
        assert spoken_final.startswith(spoken) or spoken in spoken_final
        assert "normalized" not in event.payload
    payload = finals[0].payload
    assert payload["spoken"] == spoken_final
    assert payload["spoken"] == harness.settings.asr_stub_transcript
    assert "normalized" in payload
    assert "instants" in payload
    assert "slot_conf" in payload
    assert "2:30" in str(payload["normalized"])


async def test_hanging_finish_emits_empty_asr_ok_false(harness: Harness) -> None:
    settings = harness.settings.model_copy(update={"asr_finish_timeout_ms": 40})
    pool = AsrPool.stub(settings, harness.metrics, sleep_s=0.3)
    seen: list[Event] = []

    async def forward(event: Event) -> None:
        seen.append(event)

    handler = AsrHandler(
        session=harness.session,
        settings=settings,
        engine=pool,
        metrics=harness.metrics,
        forward=forward,
    )
    harness.session.put_pcm(0, _PCM)
    await handler(harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=0))
    pool.close()
    finals = [event for event in seen if event.kind is EventKind.FINAL]
    assert len(finals) == 1
    assert finals[0].payload["asr_ok"] == 0
    assert finals[0].payload["spoken"] == ""


async def test_odd_pcm_increments_handler_error_and_pool_survives(harness: Harness) -> None:
    pool = AsrPool.stub(harness.settings, harness.metrics)
    handler = AsrHandler(
        session=harness.session,
        settings=harness.settings,
        engine=pool,
        metrics=harness.metrics,
    )
    stage = harness.stage("asr", handler)
    stage.start()
    harness.session.put_pcm(0, b"\x00")
    await stage.emit(harness.session.create_event(EventKind.AUDIO, {"samples": 1}, frame_index=0))
    for _ in range(40):
        if counter_value(harness.metrics.errors, stage="asr", reason="handler") >= 1.0:
            break
        await asyncio.sleep(0.01)
    assert counter_value(harness.metrics.errors, stage="asr", reason="handler") == 1.0
    stream = pool.start_stream("other", 0, live=lambda: 0, speaking=lambda: False)
    result = await stream.push(_PCM)
    pool.close()
    with pytest.raises(ValueError, match="even"):
        await stage.aclose()
    assert result is not None
    assert result.text != ""


async def test_hotword_list_changes_with_vocab_id(harness: Harness) -> None:
    pool = AsrPool.stub(harness.settings, harness.metrics)
    handler = AsrHandler(
        session=harness.session,
        settings=harness.settings,
        engine=pool,
        metrics=harness.metrics,
    )
    greet = handler.hotwords
    harness.session.put_pcm(0, _PCM)
    await handler(harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=0))
    assert handler.applied_hotwords == greet
    harness.session.expected_vocab_id = "doctor"
    harness.session.put_pcm(1, _PCM)
    await handler(harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=1))
    doctor = handler.hotwords
    pool.close()
    assert doctor != greet
    assert any("Lang" in item for item in doctor)
    assert handler.applied_hotwords == doctor


def test_asr_stage_does_not_import_an_llm_client() -> None:
    text = Path("pipeline/stages/asr.py").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "models.llm" not in lowered
    assert "import llm" not in lowered
    assert "openai" not in lowered
    assert "langchain" not in lowered
