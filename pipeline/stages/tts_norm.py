"""TTS text normalization. Does not import an LLM client."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from models.tts_cache import cache_key
from models.tts_pool import TtsJob
from nlp.tn import TnContext, normalize_counted
from pipeline.event import Event, EventKind, JsonValue
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.tts_norm")

Forward = Callable[[Event], Awaitable[None]]


class TtsNormHandler:
    """Consume TTS_CHUNK text, emit a TtsJob payload for audio_out."""

    __slots__ = ("_forward", "_metrics", "_session", "_settings", "emitted")

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        forward: Forward | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._forward = forward
        self.emitted = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.TTS_CHUNK:
            return
        started = time.perf_counter()
        get_current_span().set_attribute("model", "tn")
        raw = str(event.payload.get("text") or "")
        context = TnContext(
            spell_name=int(event.payload.get("spell_name") or 0) == 1,
            digit_mode=int(event.payload.get("digit_mode") or 0) == 1,
            confirm=int(event.payload.get("confirm") or 0) == 1,
        )
        spoken, unknown = normalize_counted(raw, context)
        if unknown:
            self._metrics.tn_unknown_char.inc(unknown)
        elapsed = time.perf_counter() - started
        self._metrics.tn_seconds.observe(elapsed)
        get_current_span().set_attribute("latency_ms", elapsed * 1000.0)
        speed = self._settings.tts_digit_speed if context.digit_mode else self._settings.tts_speed
        key = cache_key(spoken, self._settings.tts_voice, speed)
        job = TtsJob(
            session_id=self._session.session_id,
            generation=event.generation,
            text=spoken,
            voice=self._settings.tts_voice,
            speed=speed,
            cache_key=key,
            filler=int(event.payload.get("filler") or 0),
            first_chunk=int(event.payload.get("first_chunk") or 0) == 1,
        )
        payload: dict[str, JsonValue] = {
            "text": spoken,
            "voice": job.voice,
            "speed": job.speed,
            "cache_key": key,
            "filler": job.filler,
            "first_chunk": 1 if job.first_chunk else 0,
            "template_id": str(event.payload.get("template_id") or ""),
            "digit_mode": 1 if context.digit_mode else 0,
        }
        out = self._session.create_event(EventKind.TTS_CHUNK, payload)
        self.emitted += 1
        _LOG.info(
            "tn",
            session_id=self._session.session_id,
            digit_mode=payload["digit_mode"],
        )
        if self._forward is not None:
            await self._forward(out)
