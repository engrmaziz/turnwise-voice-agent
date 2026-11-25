"""A full inbox blocks, then fails the producer when the put timeout elapses."""

import asyncio
import time

import pytest

from pipeline.errors import StageBackpressureError
from pipeline.event import Event, EventKind
from pipeline.stage import StageConfig
from tests.conftest import Harness
from tests.support import counter_value


async def test_second_put_times_out_when_the_inbox_stays_full(harness: Harness) -> None:
    stage = harness.stage(
        "asr",
        _never,
        config=StageConfig(queue_maxsize=1, put_timeout_s=0.05),
    )
    first = harness.session.create_event(EventKind.AUDIO, {}, frame_index=0)
    second = harness.session.create_event(EventKind.AUDIO, {}, frame_index=1)
    await stage.emit(first)
    with pytest.raises(StageBackpressureError, match="asr") as caught:
        await stage.emit(second)
    assert caught.value.stage == "asr"
    assert caught.value.timeout_s == 0.05
    assert counter_value(harness.metrics.backpressure, stage="asr") == 1.0
    assert stage.inbox.qsize() == 1


async def test_put_unblocks_when_a_slot_frees(harness: Harness) -> None:
    stage = harness.stage(
        "asr",
        _never,
        config=StageConfig(queue_maxsize=1, put_timeout_s=2.0),
    )
    first = harness.session.create_event(EventKind.AUDIO, {}, frame_index=0)
    second = harness.session.create_event(EventKind.AUDIO, {}, frame_index=1)
    await stage.emit(first)

    async def send_second() -> None:
        await stage.emit(second)

    producer = asyncio.create_task(send_second())
    await asyncio.sleep(0.05)
    assert producer.done() is False
    started = time.perf_counter()
    await stage.inbox.get()
    await asyncio.wait_for(producer, timeout=1)
    assert time.perf_counter() - started < 1
    assert stage.inbox.qsize() == 1


async def _never(_event: Event) -> None:
    return
