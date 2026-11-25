"""A VAD job submitted at generation 0 is ignored after barge-in."""

from __future__ import annotations

import asyncio

from models.vad_pool import VadInference
from pipeline.event import EventKind
from pipeline.stages.vad import VadHandler
from tests.conftest import Harness


class SlowVad:
    available = True
    model_name = "slow"
    opset: int | None = None

    def __init__(self) -> None:
        self.applied: list[int] = []
        self.gate = asyncio.Event()

    def new_state(self) -> object:
        return None

    async def infer(self, pcm16: bytes, state: object, generation: int) -> VadInference:
        await self.gate.wait()
        return VadInference(probability=0.99, state=state, generation=generation)

    def close(self) -> None:
        return


async def test_result_dropped_when_generation_moves(harness: Harness) -> None:
    engine = SlowVad()
    handler = VadHandler(
        session=harness.session,
        settings=harness.settings,
        engine=engine,
        metrics=harness.metrics,
    )
    pcm = b"\x00\x00" * 320
    for index in range(2):
        harness.session.put_pcm(index, pcm)

    async def feed() -> None:
        for index in range(2):
            event = harness.session.create_event(
                EventKind.AUDIO, {"samples": 320}, frame_index=index
            )
            await handler(event)

    task = asyncio.create_task(feed())
    await asyncio.sleep(0.01)
    harness.session.barge_in()
    engine.gate.set()
    await task
    assert handler.speech_starts == 0
