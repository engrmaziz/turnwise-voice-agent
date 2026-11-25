"""Stage dispatch: stale drops, spans, handler failures, and cancellation."""

import asyncio

import pytest

from pipeline.event import Event, EventKind
from tests.conftest import Harness
from tests.support import counter_value, histogram_count


async def _idle(_event: Event) -> None:
    return


async def test_live_event_is_handled_and_spanned(harness: Harness) -> None:
    seen: list[Event] = []
    done = asyncio.Event()

    async def handler(event: Event) -> None:
        seen.append(event)
        done.set()

    stage = harness.stage("nlu", handler)
    task = stage.start()
    event = harness.session.create_event(EventKind.FINAL, {"text": "book"})
    await stage.emit(event)
    await asyncio.wait_for(done.wait(), timeout=1)
    assert seen == [event]
    assert histogram_count(harness.metrics.latency, stage="nlu") == 1.0
    spans = harness.exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "stage.nlu"
    assert span.attributes is not None
    assert span.attributes["session_id"] == event.session_id
    assert span.attributes["turn_id"] == event.turn_id
    assert span.attributes["generation"] == event.generation
    assert span.attributes["stage"] == "nlu"
    assert span.attributes["model"] == "none"
    assert "latency_ms" in span.attributes
    assert "text" not in span.attributes
    await stage.aclose()
    assert task.done()


async def test_stale_event_is_dropped_before_the_handler(harness: Harness) -> None:
    called = False

    async def handler(_event: Event) -> None:
        nonlocal called
        called = True

    stage = harness.stage("nlu", handler)
    stage.start()
    event = harness.session.create_event(EventKind.PARTIAL, {})
    harness.session.barge_in()
    await stage.emit(event)
    await asyncio.sleep(0)
    assert called is False
    assert counter_value(harness.metrics.dropped_stale, stage="nlu") == 1.0
    assert harness.exporter.get_finished_spans() == ()
    await stage.aclose()


async def test_queued_event_is_dropped_when_generation_moves(harness: Harness) -> None:
    called = False

    async def handler(_event: Event) -> None:
        nonlocal called
        called = True

    stage = harness.stage("asr", handler)
    event = harness.session.create_event(EventKind.PARTIAL, {})
    await stage.inbox.put(event)
    harness.session.barge_in()
    task = stage.start()
    for _ in range(20):
        if counter_value(harness.metrics.dropped_stale, stage="asr") >= 1.0:
            break
        await asyncio.sleep(0)
    assert called is False
    assert counter_value(harness.metrics.dropped_stale, stage="asr") == 1.0
    assert task.done() is False
    await stage.aclose()


async def test_foreign_session_is_counted_and_a_later_event_still_runs(harness: Harness) -> None:
    seen: list[str] = []
    done = asyncio.Event()

    async def handler(event: Event) -> None:
        seen.append(event.session_id)
        done.set()

    stage = harness.stage("dm", handler)
    stage.start()
    other = harness.store.open("33333333-3333-4333-8333-333333333333")
    await stage.emit(other.create_event(EventKind.NLU, {}))
    assert counter_value(harness.metrics.errors, stage="dm", reason="foreign_session") == 1.0
    await stage.emit(harness.session.create_event(EventKind.NLU, {}))
    await asyncio.wait_for(done.wait(), timeout=1)
    assert seen == [harness.session.session_id]
    await stage.aclose()


async def test_unknown_session_is_counted_and_the_stage_stays_up(harness: Harness) -> None:
    async def handler(_event: Event) -> None:
        raise AssertionError("handler ran")

    event = harness.session.create_event(EventKind.FINAL, {})
    harness.store.close(harness.session.session_id)
    stage = harness.stage("dm", handler)
    await stage.inbox.put(event)
    task = stage.start()
    for _ in range(20):
        if counter_value(harness.metrics.errors, stage="dm", reason="unknown_session") >= 1.0:
            break
        await asyncio.sleep(0)
    assert counter_value(harness.metrics.errors, stage="dm", reason="unknown_session") == 1.0
    assert task.done() is False
    await stage.aclose()


async def test_handler_exception_fails_the_task_and_cleans_up_once(harness: Harness) -> None:
    calls: list[str] = []

    async def handler(_event: Event) -> None:
        raise RuntimeError("bad parse")

    async def cleanup() -> None:
        calls.append("cleanup")

    stage = harness.stage("nlu", handler, on_cleanup=cleanup)
    task = stage.start()
    await stage.emit(harness.session.create_event(EventKind.FINAL, {}))
    with pytest.raises(RuntimeError, match="bad parse"):
        await task
    assert calls == ["cleanup"]
    assert counter_value(harness.metrics.errors, stage="nlu", reason="handler") == 1.0
    spans = harness.exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code.name == "ERROR"


async def test_cancel_runs_cleanup_once_and_reraises(harness: Harness) -> None:
    calls: list[str] = []

    async def cleanup() -> None:
        calls.append("cleanup")

    stage = harness.stage("vad", _idle, on_cleanup=cleanup)
    task = stage.start()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["cleanup"]
    assert task.cancelled()
    await stage.aclose()
    assert calls == ["cleanup"]


async def test_aclose_without_start_still_cleans_up(harness: Harness) -> None:
    calls: list[str] = []

    async def cleanup() -> None:
        calls.append("cleanup")

    stage = harness.stage("vad", _idle, on_cleanup=cleanup)
    await stage.aclose()
    await stage.aclose()
    assert calls == ["cleanup"]


async def test_start_twice_raises(harness: Harness) -> None:
    stage = harness.stage("vad", _idle)
    stage.start()
    with pytest.raises(RuntimeError, match="already running"):
        stage.start()
    await stage.aclose()


async def test_stage_name_and_config_are_validated(harness: Harness) -> None:
    from pipeline.stage import StageConfig

    with pytest.raises(ValueError, match="stage name"):
        harness.stage("VAD", _idle)
    with pytest.raises(ValueError, match="queue_maxsize"):
        StageConfig(queue_maxsize=0, put_timeout_s=0.1)
    with pytest.raises(ValueError, match="put_timeout_s"):
        StageConfig(queue_maxsize=1, put_timeout_s=0)


async def test_two_stages_forward_live_events_and_drop_stale_ones(harness: Harness) -> None:
    seen: list[Event] = []
    ready = asyncio.Event()

    async def record(event: Event) -> None:
        seen.append(event)
        ready.set()

    right = harness.stage("tts_norm", record)

    async def forward(event: Event) -> None:
        await right.emit(event)

    left = harness.stage("chunker", forward)
    right.start()
    left.start()
    live = harness.session.create_event(EventKind.SAY, {"text": "hello"})
    await left.emit(live)
    await asyncio.wait_for(ready.wait(), timeout=1)
    assert seen == [live]
    names = {span.name for span in harness.exporter.get_finished_spans()}
    assert names == {"stage.chunker", "stage.tts_norm"}

    stale = harness.session.create_event(EventKind.SAY, {"text": "old"})
    harness.session.barge_in()
    await left.emit(stale)
    assert len(seen) == 1
    assert counter_value(harness.metrics.dropped_stale, stage="chunker") == 1.0
    assert counter_value(harness.metrics.dropped_stale, stage="tts_norm") == 0.0
    await left.aclose()
    await right.aclose()
