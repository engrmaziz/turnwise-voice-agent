"""Utterance emotion on TURN_END. Must not sit on the TTFA path."""

from __future__ import annotations

import time

import structlog
from opentelemetry.trace import get_current_span

from models.emotion_pool import EmotionScorer
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.emotion")


class EmotionHandler:
    """Score concatenated utterance PCM. Timeouts leave ``last_emotion`` unchanged."""

    __slots__ = ("_metrics", "_scorer", "_session", "_settings", "emitted")

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        scorer: EmotionScorer,
        metrics: StageMetrics,
    ) -> None:
        self._session = session
        self._settings = settings
        self._scorer = scorer
        self._metrics = metrics
        self.emitted = 0

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.TURN_END:
            return
        get_current_span().set_attribute("model", self._scorer.model_name)
        pcm = _concat_pcm(self._session.snapshot_pcm())
        stamped = event.generation
        started = time.perf_counter()
        try:
            probs = await self._scorer.score(pcm, stamped)
        except TimeoutError:
            self._metrics.emotion_timeouts.inc()
            elapsed = time.perf_counter() - started
            self._metrics.emotion_seconds.observe(elapsed)
            get_current_span().set_attribute("latency_ms", elapsed * 1000.0)
            _LOG.info(
                "emotion_timeout",
                session_id=self._session.session_id,
                timeout_ms=self._settings.emotion_timeout_ms,
            )
            return
        elapsed = time.perf_counter() - started
        self._metrics.emotion_seconds.observe(elapsed)
        get_current_span().set_attribute("latency_ms", elapsed * 1000.0)
        if stamped != self._session.generation:
            return
        if probs is None:
            return
        self._session.last_emotion = probs
        self.emitted += 1


def _concat_pcm(frames: dict[int, bytes]) -> bytes:
    if not frames:
        return b""
    return b"".join(frames[index] for index in sorted(frames))
