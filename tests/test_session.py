"""Session generation, turn ids, and speaking-task cancellation."""

import asyncio

import pytest

from pipeline.errors import SessionNotFoundError
from pipeline.event import Event, EventKind
from pipeline.session import Session, SessionStore
from tests.conftest import Harness
from tests.support import counter_value


def test_rejects_empty_session_id() -> None:
    with pytest.raises(ValueError, match="session_id"):
        Session("")


def test_event_rejects_malformed_fields() -> None:
    with pytest.raises(ValueError, match="session_id"):
        Event(
            kind=EventKind.AUDIO,
            session_id="",
            turn_id=0,
            generation=0,
            frame_index=None,
            payload={},
            ts_monotonic=0.0,
        )
    with pytest.raises(ValueError, match="turn_id"):
        Event(
            kind=EventKind.AUDIO,
            session_id="s",
            turn_id=-1,
            generation=0,
            frame_index=None,
            payload={},
            ts_monotonic=0.0,
        )
    with pytest.raises(ValueError, match="frame_index"):
        Event(
            kind=EventKind.AUDIO,
            session_id="s",
            turn_id=0,
            generation=0,
            frame_index=-1,
            payload={},
            ts_monotonic=0.0,
        )


def test_payload_is_immutable(harness: Harness) -> None:
    event = harness.session.create_event(EventKind.PARTIAL, {"text": "hello"})
    with pytest.raises(TypeError):
        event.payload["text"] = "mutated"  # type: ignore[index]


def test_next_turn_does_not_change_generation(harness: Harness) -> None:
    assert harness.session.next_turn() == 1
    assert harness.session.generation == 0
    event = harness.session.create_event(EventKind.PARTIAL, {})
    assert event.turn_id == 1
    assert event.generation == 0


def test_create_event_stamps_ids_and_frame(harness: Harness) -> None:
    event = harness.session.create_event(EventKind.AUDIO, {"rms": 0.1}, frame_index=4)
    assert event.session_id == harness.session.session_id
    assert event.turn_id == 0
    assert event.generation == 0
    assert event.frame_index == 4
    assert event.payload["rms"] == 0.1


def test_is_stale_for_generation_and_other_session(harness: Harness) -> None:
    event = harness.session.create_event(EventKind.FINAL, {})
    assert harness.session.is_stale(event) is False
    harness.session.barge_in()
    assert harness.session.is_stale(event) is True
    other = Session("22222222-2222-4222-8222-222222222222")
    foreign = other.create_event(EventKind.FINAL, {})
    assert harness.session.is_stale(foreign) is True


def test_barge_in_bumps_generation_and_turn_and_records_metric(harness: Harness) -> None:
    harness.session.barge_in()
    assert harness.session.generation == 1
    assert harness.session.turn_id == 1
    assert counter_value(harness.metrics.barge_in) == 1.0
    event = harness.session.create_event(EventKind.BARGE_IN, {})
    assert event.generation == 1
    assert event.turn_id == 1


async def test_barge_in_cancels_tracked_task_and_runs_its_cleanup(harness: Harness) -> None:
    cleaned = asyncio.Event()

    async def speak() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleaned.set()
            raise

    task = asyncio.create_task(speak())
    await asyncio.sleep(0)
    harness.session.track_speaking(task)
    assert harness.session.speaking_task_count == 1
    harness.session.barge_in()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()
    assert harness.session.speaking_task_count == 0


async def test_barge_in_from_inside_the_speaking_task(harness: Harness) -> None:
    reached: list[str] = []

    async def speak() -> None:
        current = asyncio.current_task()
        assert current is not None
        harness.session.track_speaking(current)
        harness.session.barge_in()
        await asyncio.sleep(0)
        reached.append("after")

    task = asyncio.create_task(speak())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert reached == []
    assert harness.session.generation == 1
    assert harness.session.turn_id == 1


async def test_finished_task_is_not_tracked(harness: Harness) -> None:
    async def speak() -> None:
        return

    task = asyncio.create_task(speak())
    await task
    harness.session.track_speaking(task)
    assert harness.session.speaking_task_count == 0


async def test_completed_task_leaves_the_speaking_set(harness: Harness) -> None:
    release = asyncio.Event()

    async def speak() -> None:
        await release.wait()

    task = asyncio.create_task(speak())
    await asyncio.sleep(0)
    harness.session.track_speaking(task)
    assert harness.session.speaking_task_count == 1
    release.set()
    await task
    await asyncio.sleep(0)
    assert harness.session.speaking_task_count == 0


def test_store_rejects_duplicate_and_missing_sessions() -> None:
    store = SessionStore()
    store.open("a")
    with pytest.raises(ValueError, match="already open"):
        store.open("a")
    store.close("a")
    with pytest.raises(SessionNotFoundError, match="unknown session_id"):
        store.get("a")
