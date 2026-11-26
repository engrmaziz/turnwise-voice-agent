"""Hybrid endpointer. Digit patience runs before completeness probability."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from models.onnx_pool import TurnScorer, TurnUnavailableError
from pipeline.audio.quality import rms_full_scale
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.endpoint")

Forward = Callable[[Event], Awaitable[None]]
_DIGIT_SLOTS = frozenset({"phone", "dob"})


def should_end_turn(
    silence_ms: float,
    text: str,
    p_complete: float,
    expected_slot: str,
    settings: Settings,
) -> bool:
    """Return whether the caller has finished this utterance.

    Order is locked by ``tests/test_endpoint_policy.py``. Digit patience runs
    before ``p_complete`` so a high score cannot cut a phone number early.
    Digit slots also skip the 1200 ms hard ceiling and the 800 ms default;
    they use ``endpoint_digit_hard_ms`` instead.
    """
    if not text.strip():
        return False
    digit = expected_slot in _DIGIT_SLOTS
    if digit and silence_ms < settings.endpoint_digit_patience_ms:
        return False
    if digit and silence_ms >= settings.endpoint_digit_hard_ms:
        return True
    if not digit and silence_ms >= settings.endpoint_hard_silence_ms:
        return True
    if p_complete >= settings.endpoint_high_p and silence_ms >= settings.endpoint_high_silence_ms:
        return True
    if p_complete >= settings.endpoint_mid_p and silence_ms >= settings.endpoint_mid_silence_ms:
        return True
    if digit:
        return False
    return silence_ms >= settings.endpoint_default_silence_ms


class EndpointHandler:
    """Latch: one ``TURN_END`` until the next speech start."""

    __slots__ = (
        "_closed",
        "_forward",
        "_last_speech_mono",
        "_metrics",
        "_scorer",
        "_session",
        "_settings",
        "_text",
        "turn_ends",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        scorer: TurnScorer,
        forward: Forward | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._scorer = scorer
        self._forward = forward
        self._closed = False
        self._text = ""
        self._last_speech_mono = time.monotonic()
        self.turn_ends = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.PARTIAL:
            spoken = event.payload.get("spoken")
            if isinstance(spoken, str):
                self._text = spoken
                self._session.stable_prefix = spoken
            return
        if event.kind is EventKind.FINAL:
            return
        if event.kind is EventKind.TURN_END or event.kind is EventKind.SESSION_END:
            return
        if event.kind is not EventKind.AUDIO or event.frame_index is None:
            return
        pcm = self._session.get_pcm(event.frame_index)
        if pcm is None:
            return
        now = time.monotonic()
        if rms_full_scale(pcm) > self._settings.audio_silence_rms:
            self.note_speech(now=now)
            return
        silence_ms = (now - self._last_speech_mono) * 1000.0
        await self.evaluate_silence(silence_ms, frame_index=event.frame_index)

    def note_text(self, text: str) -> None:
        self._text = text
        self._session.stable_prefix = text

    def note_speech(self, *, now: float | None = None) -> None:
        self._last_speech_mono = time.monotonic() if now is None else now
        if self._closed:
            self._closed = False
            self._text = ""

    async def evaluate_silence(
        self,
        silence_ms: float,
        *,
        frame_index: int | None = None,
    ) -> Event | None:
        """Apply the policy once. Latched until ``note_speech`` after a ``TURN_END``."""
        if self._closed:
            return None
        p_complete = await self._p_complete()
        end = should_end_turn(
            silence_ms,
            self._text,
            p_complete,
            self._session.expected_slot,
            self._settings,
        )
        self._metrics.endpoint_silence.observe(silence_ms)
        result = "end" if end else "hold"
        self._metrics.endpoint_decisions.labels(result=result).inc()
        span = get_current_span()
        span.set_attribute("model", self._scorer.model_name)
        if not end:
            return None
        self._closed = True
        self.turn_ends += 1
        turn_end = self._session.create_event(
            EventKind.TURN_END,
            {"reason": "endpoint", "silence_ms": int(silence_ms)},
            frame_index=frame_index,
        )
        self._session.turn_end_ts = time.monotonic()
        _LOG.info("turn_end", session_id=self._session.session_id, silence_ms=int(silence_ms))
        if self._forward is not None:
            await self._forward(turn_end)
        return turn_end

    async def _p_complete(self) -> float:
        if not self._settings.turn_model_enabled:
            return 0.0
        started = time.perf_counter()
        try:
            score = await self._scorer.p_complete(self._text, self._session.expected_slot)
        except TimeoutError:
            self._metrics.turn_model_timeouts.inc()
            return 0.0
        except TurnUnavailableError:
            return 0.0
        self._metrics.turn_model_seconds.observe(time.perf_counter() - started)
        return score
