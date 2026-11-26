"""A speaking session cuts in front of an idle job under a stub delay."""

import asyncio
import time

from models.llm_client import LlmClient, ProposalSchema


async def test_speaking_job_finishes_before_idle_when_queued_together() -> None:
    client = LlmClient.stub(
        timeout_ms=5000,
        response='{"intent":"book","slots":{}}',
        sleep_s=0.05,
        max_batch=1,
    )
    client.hold_dispatch()
    idle_task = asyncio.create_task(client.complete_json("idle", ProposalSchema, speaking=False))
    speaking_task = asyncio.create_task(
        client.complete_json("speak", ProposalSchema, speaking=True)
    )
    await asyncio.sleep(0)
    started = time.perf_counter()
    finished: dict[str, float] = {}

    async def mark(name: str, task: asyncio.Task[object]) -> None:
        await task
        finished[name] = time.perf_counter() - started

    client.release_dispatch()
    await asyncio.gather(mark("idle", idle_task), mark("speaking", speaking_task))
    assert finished["speaking"] < finished["idle"]
