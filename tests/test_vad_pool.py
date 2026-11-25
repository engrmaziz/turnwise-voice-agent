"""VAD pool uses an executor and drops stale generations."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import patch

from models.vad_pool import VadInference, VadPool


def test_infer_runs_off_the_event_loop() -> None:
    main = threading.get_ident()
    seen: list[int] = []

    def infer_sync(_pcm: bytes, state: object, generation: int) -> VadInference:
        seen.append(threading.get_ident())
        return VadInference(probability=0.1, state=state, generation=generation)

    pool = VadPool(
        available=True,
        timeout_s=1.0,
        infer_sync=infer_sync,
        new_state=lambda: None,
    )

    async def run() -> None:
        result = await pool.infer(b"\x00\x00" * 512, None, 0)
        assert result.probability == 0.1

    asyncio.run(run())
    pool.close()
    assert seen
    assert seen[0] != main


def test_infer_patches_executor_not_inline() -> None:
    order: list[str] = []

    def infer_sync(_pcm: bytes, state: object, generation: int) -> VadInference:
        order.append("sync")
        return VadInference(probability=0.2, state=state, generation=generation)

    pool = VadPool(
        available=True,
        timeout_s=1.0,
        infer_sync=infer_sync,
        new_state=lambda: None,
    )

    async def run() -> None:
        loop = asyncio.get_running_loop()
        original = loop.run_in_executor

        def wrapped(*args: object, **kwargs: object) -> object:
            order.append("executor")
            return original(*args, **kwargs)  # type: ignore[arg-type]

        with patch.object(loop, "run_in_executor", wrapped):
            await pool.infer(b"\x00\x00" * 512, None, 0)

    asyncio.run(run())
    pool.close()
    assert order
    assert order[0] == "executor"
    assert "sync" in order


def test_stale_generation_is_visible_to_caller() -> None:
    def infer_sync(_pcm: bytes, state: object, generation: int) -> VadInference:
        time.sleep(0.05)
        return VadInference(probability=0.9, state=state, generation=generation)

    pool = VadPool(
        available=True,
        timeout_s=1.0,
        infer_sync=infer_sync,
        new_state=lambda: None,
    )

    async def run() -> None:
        live = 0
        result = await pool.infer(b"\x00\x00" * 512, None, live)
        assert result.generation == live
        stale = result.generation != 1

        async def submit() -> VadInference:
            return await pool.infer(b"\x00\x00" * 512, None, 0)

        task = asyncio.create_task(submit())
        await asyncio.sleep(0)
        dropped = await task
        assert dropped.generation == 0
        assert stale is True

    asyncio.run(run())
    pool.close()


def test_timeout_raises() -> None:
    def infer_sync(_pcm: bytes, state: object, generation: int) -> VadInference:
        time.sleep(0.2)
        return VadInference(probability=0.1, state=state, generation=generation)

    pool = VadPool(
        available=True,
        timeout_s=0.02,
        infer_sync=infer_sync,
        new_state=lambda: None,
    )

    async def run() -> None:
        try:
            await pool.infer(b"\x00\x00" * 512, None, 0)
        except TimeoutError:
            return
        raise AssertionError("expected timeout")

    asyncio.run(run())
    pool.close()
