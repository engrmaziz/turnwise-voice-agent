"""Barge-in gates: AEC, sustained VAD speech, and a non-backchannel partial."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from nlp.backchannel import is_backchannel
from pipeline.audio.quality import rms_full_scale
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings
from server.playback import PlaybackCursor

_LOG = structlog.get_logger("pipeline.stages.barge")

Forward = Callable[[Event], Awaitable[None]]


class BargeHandler:
    """Fires once per agent utterance when every gate passes."""

    __slots__ = (
        "_fired",
        "_forward",
        "_metrics",
        "_partial",
        "_playback",
        "_session",
        "_settings",
        "_speech_ms",
        "_speech_started_mono",
        "hits",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        playback: PlaybackCursor,
        forward: Forward | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._playback = playback
        self._forward = forward
        self._speech_ms = 0.0
        self._speech_started_mono: float | None = None
        self._partial = ""
        self._fired = False
        self.hits = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.PARTIAL:
            spoken = event.payload.get("spoken")
            if isinstance(spoken, str):
                self._partial = spoken
                self._session.stable_prefix = spoken
            await self._maybe_fire(event, label=None)
            return
        if event.kind is EventKind.TURN_END:
            self._reset()
            return
        if event.kind is not EventKind.AUDIO or event.frame_index is None:
            return
        if self._session.speaking_task_count <= 0:
            self._reset()
            return
        pcm = self._session.get_pcm(event.frame_index)
        if pcm is None:
            return
        if rms_full_scale(pcm) <= self._settings.audio_silence_rms:
            return
        self._speech_ms += self._settings.ws_frame_ms
        if self._speech_started_mono is None:
            self._speech_started_mono = time.monotonic()
        await self._maybe_fire(event, label=None)

    async def consider(self, event: Event, *, should_barge: bool | None) -> bool:
        """Test entry: inject a labeled fixture. Production uses ``__call__``."""
        return await self._maybe_fire(event, label=should_barge)

    async def _maybe_fire(self, event: Event, label: bool | None) -> bool:
        if self._fired:
            return False
        if self._session.speaking_task_count <= 0:
            return False
        if not self._session.barge_in_enabled:
            return False
        duration = self._speech_ms
        phrases = self._settings.backchannel_list
        if is_backchannel(
            self._partial,
            expected_slot=self._session.expected_slot,
            duration_ms=duration,
            phrases=phrases,
            max_ms=self._settings.backchannel_max_ms,
        ):
            self._metrics.backchannel_ignored.inc()
            return False
        if not self._partial.strip():
            if label is True:
                self._metrics.missed_barge_in.inc()
            return False
        if self._speech_ms < self._settings.barge_in_min_speech_ms:
            if label is True:
                self._metrics.missed_barge_in.inc()
            return False
        saved = self._session.snapshot_pcm()
        prefix = self._playback.prefix_for_ack(self._playback.acked_frame)
        if not self._playback.has_chunks:
            self._metrics.playback_unmap.inc()
            prefix = ""
        t_barge = time.perf_counter()
        self._session.request_barge_in()
        self._session.played_text = prefix
        self._session.restore_pcm(saved)
        self._fired = True
        self.hits += 1
        if label is False:
            self._metrics.false_barge_in.inc()
        self._metrics.cancel_latency.observe(max(0.0, time.perf_counter() - t_barge))
        span = get_current_span()
        span.set_attribute("model", "none")
        barge = self._session.create_event(
            EventKind.BARGE_IN,
            {"played_text": prefix},
            frame_index=event.frame_index,
        )
        _LOG.info("barge_in", session_id=self._session.session_id, played_chars=len(prefix))
        if self._forward is not None:
            await self._forward(barge)
        return True

    def note_speech_ms(self, speech_ms: float) -> None:
        self._speech_ms = speech_ms
        if speech_ms > 0 and self._speech_started_mono is None:
            self._speech_started_mono = time.monotonic()

    def note_partial(self, text: str) -> None:
        self._partial = text

    def _reset(self) -> None:
        self._speech_ms = 0.0
        self._speech_started_mono = None
        self._partial = ""
        self._fired = False
