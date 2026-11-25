"""One asyncio task, one bounded inbox, stale events dropped before the handler."""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog
from opentelemetry.trace import Status, StatusCode, Tracer

from pipeline.errors import SessionNotFoundError, StageBackpressureError
from pipeline.event import Event
from pipeline.metrics import StageMetrics
from pipeline.session import SessionStore

# Dashboards group by model. Stages that do not call a model still set the
# attribute so a missing label is not confused with a forgotten one.
NO_MODEL = "none"

_STAGE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_LOG = structlog.get_logger("pipeline.stage")

StageHandler = Callable[[Event], Awaitable[None]]
CleanupHook = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class StageConfig:
    """Queue bounds for one stage. Taken from process settings at construction."""

    queue_maxsize: int
    put_timeout_s: float

    def __post_init__(self) -> None:
        if self.queue_maxsize < 1:
            raise ValueError("queue_maxsize must be >= 1")
        if self.put_timeout_s <= 0:
            raise ValueError("put_timeout_s must be > 0")


class Stage:
    """Per-session stage task.

    A full inbox waits, then raises ``StageBackpressureError``. An unbounded
    queue would accept events the consumer cannot hear and hide the latency.
    Stale events are dropped: barge-in is a normal path, not a handler error.
    A foreign session id is logged and counted, and the stage keeps running so
    one misrouted event does not end the call. The owner still treats a rising
    foreign-session counter as a routing bug.
    """

    __slots__ = (
        "_cleaned",
        "_config",
        "_handler",
        "_inbox",
        "_metrics",
        "_name",
        "_on_cleanup",
        "_session_id",
        "_sessions",
        "_task",
        "_tracer",
    )

    def __init__(
        self,
        *,
        name: str,
        session_id: str,
        sessions: SessionStore,
        handler: StageHandler,
        config: StageConfig,
        tracer: Tracer,
        metrics: StageMetrics,
        on_cleanup: CleanupHook | None = None,
    ) -> None:
        if _STAGE_NAME.fullmatch(name) is None:
            raise ValueError("stage name must match [a-z][a-z0-9_]{0,63}")
        if not session_id:
            raise ValueError("session_id must be non-empty")
        self._name = name
        self._session_id = session_id
        self._sessions = sessions
        self._handler = handler
        self._config = config
        self._tracer = tracer
        self._metrics = metrics
        self._on_cleanup = _noop_cleanup if on_cleanup is None else on_cleanup
        self._inbox: asyncio.Queue[Event] = asyncio.Queue(maxsize=config.queue_maxsize)
        self._task: asyncio.Task[None] | None = None
        self._cleaned = False
        metrics.queue_depth.labels(stage=name).set(0)

    @property
    def name(self) -> str:
        return self._name

    @property
    def inbox(self) -> asyncio.Queue[Event]:
        """Bounded inbox. Tests inject events that bypass ``emit``'s stale check."""

        return self._inbox

    async def emit(self, event: Event) -> None:
        """Enqueue ``event`` or raise ``StageBackpressureError``.

        The timeout is what turns a stuck consumer into a failed producer.
        Without it, await on a full queue grows latency with no metric.
        """
        if self._drop_before_queue(event):
            return
        try:
            await asyncio.wait_for(self._inbox.put(event), timeout=self._config.put_timeout_s)
        except TimeoutError as exc:
            self._metrics.backpressure.labels(stage=self._name).inc()
            raise StageBackpressureError(self._name, self._config.put_timeout_s) from exc
        self._metrics.queue_depth.labels(stage=self._name).set(self._inbox.qsize())

    def start(self) -> asyncio.Task[None]:
        if self._task is not None and not self._task.done():
            raise RuntimeError(f"stage {self._name} is already running")
        self._task = asyncio.create_task(self.run(), name=f"stage:{self._name}")
        return self._task

    async def run(self) -> None:
        try:
            while True:
                event = await self._inbox.get()
                try:
                    await self._dispatch(event)
                finally:
                    self._inbox.task_done()
                    self._metrics.queue_depth.labels(stage=self._name).set(self._inbox.qsize())
        except asyncio.CancelledError:
            await self._finish_cancelled()
        except Exception:
            await self._cleanup_once()
            raise

    async def aclose(self) -> None:
        """Cancel the stage task and wait until its cleanup has finished."""
        task = self._task
        if task is None:
            await self._cleanup_once()
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    async def _dispatch(self, event: Event) -> None:
        if self._should_drop(event, count=True):
            return
        started = time.perf_counter()
        with self._tracer.start_as_current_span(f"stage.{self._name}") as span:
            span.set_attribute("session_id", event.session_id)
            span.set_attribute("turn_id", event.turn_id)
            span.set_attribute("generation", event.generation)
            span.set_attribute("stage", self._name)
            span.set_attribute("model", NO_MODEL)
            structlog.contextvars.bind_contextvars(
                session_id=event.session_id,
                turn_id=event.turn_id,
                generation=event.generation,
                stage=self._name,
            )
            try:
                await self._handler(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._metrics.errors.labels(stage=self._name, reason="handler").inc()
                _LOG.exception("stage_handler_failed", stage=self._name)
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                elapsed = time.perf_counter() - started
                span.set_attribute("latency_ms", elapsed * 1000.0)
                self._metrics.latency.labels(stage=self._name).observe(elapsed)
                structlog.contextvars.unbind_contextvars(
                    "session_id",
                    "turn_id",
                    "generation",
                    "stage",
                )

    def _drop_before_queue(self, event: Event) -> bool:
        return self._should_drop(event, count=True)

    def _should_drop(self, event: Event, *, count: bool) -> bool:
        if event.session_id != self._session_id:
            if count:
                self._metrics.errors.labels(stage=self._name, reason="foreign_session").inc()
                _LOG.warning(
                    "foreign_session_event",
                    stage=self._name,
                    session_id=event.session_id,
                    bound_session_id=self._session_id,
                )
            return True
        try:
            session = self._sessions.get(self._session_id)
        except SessionNotFoundError:
            if count:
                self._metrics.errors.labels(stage=self._name, reason="unknown_session").inc()
                _LOG.error("session_missing", stage=self._name, session_id=self._session_id)
            return True
        if session.is_stale(event):
            if count:
                self._metrics.dropped_stale.labels(stage=self._name).inc()
                _LOG.debug(
                    "stale_event_dropped",
                    stage=self._name,
                    session_id=event.session_id,
                    turn_id=event.turn_id,
                    generation=event.generation,
                )
            return True
        return False

    async def _finish_cancelled(self) -> None:
        current = asyncio.current_task()
        if current is not None:
            # Python 3.11 re-raises CancelledError at every await while
            # cancelling() > 0, which would skip resource cleanup.
            while current.cancelling():
                current.uncancel()
        await self._cleanup_once()
        raise asyncio.CancelledError

    async def _cleanup_once(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        await self._on_cleanup()


async def _noop_cleanup() -> None:
    """Stages with no external resources still have one cleanup path."""
    return
