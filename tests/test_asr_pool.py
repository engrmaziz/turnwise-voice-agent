"""ASR pool drops stale generations and serves speaking sessions first."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

import pytest

from models.asr_pool import AsrBackendError, AsrPool
from tests.conftest import Harness
from tests.support import counter_value

_PCM = b"\x00\x00" * 320


async def test_result_dropped_after_barge_in(harness: Harness) -> None:
    pool = AsrPool.stub(harness.settings, harness.metrics, sleep_s=0.08)
    stream = pool.start_stream(
        harness.session.session_id,
        harness.session.generation,
        live=lambda: harness.session.generation,
        speaking=lambda: False,
    )
    task = asyncio.create_task(stream.push(_PCM))
    await asyncio.sleep(0.01)
    harness.session.barge_in()
    result = await task
    pool.close()
    assert result is None
    assert counter_value(harness.metrics.asr_dropped_generation) == 1.0


async def test_speaking_session_completes_first(harness: Harness) -> None:
    pool = AsrPool.stub(harness.settings, harness.metrics, sleep_s=0.05)
    occupy = pool.start_stream("occupy", 0, live=lambda: 0, speaking=lambda: False)
    idle = pool.start_stream("idle", 0, live=lambda: 0, speaking=lambda: False)
    talk = pool.start_stream("talk", 0, live=lambda: 0, speaking=lambda: True)
    order: list[str] = []

    async def mark(name: str, coro: Awaitable[object]) -> None:
        await coro
        order.append(name)

    blocker = asyncio.create_task(occupy.push(_PCM))
    await asyncio.sleep(0.01)
    idle_task = asyncio.create_task(mark("idle", idle.push(_PCM)))
    talk_task = asyncio.create_task(mark("talk", talk.push(_PCM)))
    await asyncio.gather(blocker, idle_task, talk_task)
    pool.close()
    assert order.index("talk") < order.index("idle")


def test_load_real_refuses_empty_backend(harness: Harness) -> None:
    empty = harness.settings.model_copy(update={"asr_backend": ""})
    with pytest.raises(AsrBackendError, match="empty"):
        AsrPool.load_real(empty, harness.metrics)
