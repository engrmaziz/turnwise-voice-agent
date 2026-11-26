"""Tool timeout wrapper. The 300 ms filler does not cancel the tool."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ToolOutcome(Generic[T]):
    value: T | None
    filler: bool
    timed_out: bool


async def run_with_filler(
    awaitable: Awaitable[T],
    *,
    filler_s: float,
    hard_s: float,
    on_filler: Callable[[], Awaitable[None]] | None = None,
) -> ToolOutcome[T]:
    """Race a filler timer against the tool. Hard timeout cancels the await."""
    task = asyncio.ensure_future(awaitable)
    filler_fired = False
    try:
        done, _pending = await asyncio.wait({task}, timeout=filler_s)
        if not done:
            filler_fired = True
            if on_filler is not None:
                await on_filler()
        try:
            value = await asyncio.wait_for(
                asyncio.shield(task), timeout=max(0.0, hard_s - filler_s)
            )
        except TimeoutError:
            task.cancel()
            return ToolOutcome(value=None, filler=filler_fired, timed_out=True)
        return ToolOutcome(value=value, filler=filler_fired, timed_out=False)
    except asyncio.CancelledError:
        task.cancel()
        raise
