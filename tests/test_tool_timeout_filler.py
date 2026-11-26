"""A 400 ms tool emits filler then succeeds. Timestamp delta is recorded."""

import asyncio
import json
import time
from pathlib import Path

from tools.timeouts import run_with_filler


async def test_filler_then_success_writes_delta() -> None:
    started = time.perf_counter()
    filler_at: list[float] = []

    async def on_filler() -> None:
        filler_at.append(time.perf_counter() - started)

    async def slow() -> str:
        await asyncio.sleep(0.4)
        return "booked"

    outcome = await run_with_filler(slow(), filler_s=0.3, hard_s=1.5, on_filler=on_filler)
    assert outcome.filler is True
    assert outcome.timed_out is False
    assert outcome.value == "booked"
    assert filler_at
    delta_ms = filler_at[0] * 1000.0
    assert 200.0 <= delta_ms <= 550.0
    await asyncio.to_thread(_write_filler_delta, delta_ms)


def _write_filler_delta(delta_ms: float) -> None:
    path = Path("docs/results/phase6_filler.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "filler_delta_ms": round(delta_ms, 3),
                "tool_sleep_s": 0.4,
                "tool_filler_after_ms": 300,
                "success": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
