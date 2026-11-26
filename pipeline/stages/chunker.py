"""Split SAY text into TTS clauses. Max-hold flushes whole words."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from nlp.chunker import chunk_stream, hold_prefix
from pipeline.event import Event, EventKind, JsonValue
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.chunker")

Forward = Callable[[Event], Awaitable[None]]
SleepFn = Callable[[float], Awaitable[None]]
ClockFn = Callable[[], float]


class ChunkerHandler:
    """One instance per call. A complete SAY is chunked; hold covers no-boundary text."""

    __slots__ = (
        "_buffer",
        "_clock",
        "_first",
        "_forward",
        "_hold_task",
        "_metrics",
        "_payload",
        "_session",
        "_settings",
        "_sleep",
        "emitted",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        forward: Forward | None = None,
        clock: ClockFn | None = None,
        sleep: SleepFn | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._forward = forward
        self._clock = clock if clock is not None else time.monotonic
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._buffer = ""
        self._first = True
        self._payload: dict[str, JsonValue] = {}
        self._hold_task: asyncio.Task[None] | None = None
        self.emitted = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.BARGE_IN:
            await self._cancel_hold()
            self._buffer = ""
            self._first = True
            return
        if event.kind is not EventKind.SAY:
            return
        get_current_span().set_attribute("model", "none")
        self._payload = dict(event.payload)
        self._buffer = str(event.payload.get("text") or "")
        self._first = True
        await self._cancel_hold()
        await self._emit_ready()
        if self._buffer.strip():
            self._hold_task = asyncio.create_task(self._hold())
            self._session.track_speaking(self._hold_task)

    async def _emit_ready(self) -> None:
        while self._buffer.strip():
            flushed, rest = chunk_stream(self._buffer, self._first, self._settings)
            if not flushed:
                break
            for piece in flushed:
                await self._emit_chunk(piece, reason="boundary")
            self._buffer = rest
            self._first = False

    async def _hold(self) -> None:
        try:
            started = self._clock()
            await self._sleep(self._settings.tts_max_hold_ms / 1000.0)
            held_ms = (self._clock() - started) * 1000.0
            if not self._buffer.strip():
                return
            head, rest = hold_prefix(self._buffer)
            self._buffer = rest
            if head:
                _LOG.info("chunk_hold", session_id=self._session.session_id, held_ms=held_ms)
                await self._emit_chunk(head, reason="hold")
            self._first = False
        except asyncio.CancelledError:
            raise

    async def _emit_chunk(self, text: str, *, reason: str) -> None:
        self._metrics.chunk_flush.labels(reason=reason).inc()
        payload: dict[str, JsonValue] = dict(self._payload)
        payload["text"] = text
        payload["first_chunk"] = 1 if self._first else 0
        event = self._session.create_event(EventKind.TTS_CHUNK, payload)
        self.emitted += 1
        _LOG.info(
            "chunk_flush",
            session_id=self._session.session_id,
            reason=reason,
            first_chunk=payload["first_chunk"],
        )
        if self._forward is not None:
            await self._forward(event)

    async def drain(self) -> None:
        """Wait out or cancel a leftover hold so the next turn starts clean."""
        await self._cancel_hold()

    async def _cancel_hold(self) -> None:
        task = self._hold_task
        self._hold_task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return
