"""Fuse audio, text, and dialogue signals. Does not own urgency."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from dialogue.frustration import FrustrationLatch
from nlp.fusion import fuse
from nlp.sentiment import sentiment_score
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.fusion")

Forward = Callable[[Event], Awaitable[None]]


class FusionHandler:
    """Consume NLU, stamp a fusion score, forward unchanged otherwise."""

    __slots__ = (
        "_forward",
        "_latch",
        "_metrics",
        "_session",
        "_settings",
        "emitted",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        forward: Forward | None = None,
        latch: FrustrationLatch | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._forward = forward
        self._latch = latch if latch is not None else FrustrationLatch()
        self.emitted = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    @property
    def latch(self) -> FrustrationLatch:
        return self._latch

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.NLU:
            return
        get_current_span().set_attribute("model", "fuse")
        spoken = str(event.payload.get("spoken") or "")
        text_score: float | None = None
        if self._settings.sentiment_enabled:
            # sentiment_model_enabled is false; the lexicon is the only scorer.
            text_score = sentiment_score(spoken)
        audio = self._session.last_emotion
        if audio is not None and audio.generation != self._session.generation:
            audio = None
        barged = self._session.take_barged()
        score = fuse(
            audio,
            text_score,
            self._session.repair_count,
            self._session.repeated_no,
            barged,
            self._settings,
        )
        self._metrics.fusion_score.observe(score)
        self._session.fusion_score = score
        was_latched = self._latch.offer_human
        latched = self._latch.note(score, self._settings)
        self._session.offer_human = latched
        if latched and not was_latched:
            self._metrics.offer_human.inc()
        if self._latch.take_offer_say():
            self._session.note_offer_say()
        self.emitted += 1
        _LOG.info(
            "fusion",
            session_id=self._session.session_id,
            score=round(score, 4),
            offer_human=latched,
        )
        if self._forward is not None:
            await self._forward(event)
