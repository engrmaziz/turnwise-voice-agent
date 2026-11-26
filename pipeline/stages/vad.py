"""Speech-start stage. ONNX probability plus hysteresis, pre-roll, and quality."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from models.vad_pool import VadEngine, VadUnavailableError
from pipeline.audio.preroll import Preroll
from pipeline.audio.quality import QualityWindow, rms_full_scale
from pipeline.audio.vad_gate import VadGateConfig, VadMode, VadTracker, vad_decision
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import AudioQuality, Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.vad")

Forward = Callable[[Event], Awaitable[None]]


class VadHandler:
    """One instance per call. RNN state resets on barge-in generation change."""

    __slots__ = (
        "_closed",
        "_engine",
        "_fallback_streak",
        "_forward",
        "_gate",
        "_generation",
        "_last_prob",
        "_metrics",
        "_pending",
        "_preroll",
        "_quality",
        "_session",
        "_settings",
        "_state",
        "_timeouts",
        "_tracker",
        "_window_bytes",
        "speech_starts",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        engine: VadEngine,
        metrics: StageMetrics,
        forward: Forward | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._engine = engine
        self._metrics = metrics
        self._forward = forward
        self._gate = VadGateConfig(
            threshold=settings.vad_speech_threshold,
            start_ms=settings.vad_speech_start_ms,
            max_utterance_ms=settings.vad_max_utterance_ms,
            frame_ms=settings.ws_frame_ms,
        )
        self._preroll = Preroll(settings.vad_preroll_frames)
        self._quality = QualityWindow(
            frame_ms=settings.ws_frame_ms,
            window_s=settings.audio_silence_window_s,
            clip_peak=settings.audio_clip_peak,
        )
        self._tracker = VadTracker()
        self._state = engine.new_state()
        self._generation = session.generation
        self._pending = bytearray()
        self._window_bytes = settings.vad_window_samples * 2
        self._timeouts = 0
        self._fallback_streak = 0
        self._last_prob = 0.0
        self._closed = False
        self.speech_starts = 0

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.SESSION_END:
            return
        if event.kind is not EventKind.AUDIO or event.frame_index is None:
            return
        if self._closed:
            return
        self._sync_generation()
        pcm = self._session.get_pcm(event.frame_index)
        if pcm is None:
            return
        self._quality.push(pcm)
        await self._maybe_quality(event)
        span = get_current_span()
        span.set_attribute("audio_quality", self._session.audio_quality.value)
        span.set_attribute("model", self._engine.model_name)
        if self._closed:
            return
        prob = await self._probability(pcm)
        self._metrics.vad_prob.observe(prob)
        step = vad_decision(prob, self._tracker, self._gate)
        self._tracker = step.tracker
        if step.hang:
            self._metrics.vad_hang.inc()
            self._preroll.reset()
            _LOG.info("vad_hang", session_id=self._session.session_id)
            if self._forward is not None:
                hang = self._session.create_event(
                    EventKind.TURN_END,
                    {"reason": "vad_hang"},
                    frame_index=event.frame_index,
                )
                await self._forward(hang)
        if step.speech_started:
            await self._on_speech_start(event, pcm)
        elif (
            self._tracker.mode is VadMode.IN_SPEECH and not step.hang and self._forward is not None
        ):
            await self._forward(event)
        self._preroll.push(pcm)

    def _sync_generation(self) -> None:
        if self._session.generation == self._generation:
            return
        self._generation = self._session.generation
        self._state = self._engine.new_state()
        self._tracker = VadTracker()
        self._pending.clear()
        self._timeouts = 0
        self._fallback_streak = 0
        self._last_prob = 0.0

    async def _probability(self, pcm: bytes) -> float:
        if self._use_energy():
            self._enter_fallback()
            return 1.0 if rms_full_scale(pcm) > self._settings.audio_silence_rms else 0.0
        self._pending.extend(pcm)
        while len(self._pending) >= self._window_bytes:
            window = bytes(self._pending[: self._window_bytes])
            del self._pending[: self._window_bytes]
            started = time.perf_counter()
            try:
                result = await self._engine.infer(window, self._state, self._generation)
            except TimeoutError:
                self._timeouts += 1
                if self._timeouts >= 2:
                    self._enter_fallback()
                    return 1.0 if rms_full_scale(pcm) > self._settings.audio_silence_rms else 0.0
                return self._last_prob
            except VadUnavailableError:
                self._enter_fallback()
                return 1.0 if rms_full_scale(pcm) > self._settings.audio_silence_rms else 0.0
            self._metrics.vad_latency.observe(time.perf_counter() - started)
            if result.generation != self._session.generation:
                return 0.0
            self._timeouts = 0
            self._state = result.state
            self._last_prob = result.probability
        return self._last_prob

    def _use_energy(self) -> bool:
        return self._fallback_streak > 0 or not self._engine.available

    def _enter_fallback(self) -> None:
        if self._fallback_streak == 0:
            self._metrics.vad_fallback.inc()
        self._fallback_streak = 1

    async def _on_speech_start(self, event: Event, pcm: bytes) -> None:
        self.speech_starts += 1
        snapshot = self._preroll.snapshot(pcm)
        if len(self._preroll) < self._settings.vad_preroll_frames:
            self._metrics.preroll_underrun.inc()
        start_index = event.frame_index if event.frame_index is not None else 0
        _LOG.info(
            "vad_speech_start",
            session_id=self._session.session_id,
            frame_index=event.frame_index,
            preroll_bytes=len(snapshot),
        )
        if self._session.speaking_task_count > 0:
            self._session.request_barge_in()
            self._generation = self._session.generation
            self._state = self._engine.new_state()
        self._session.put_pcm(start_index, snapshot)
        if self._forward is not None:
            await self._forward(event)

    async def _maybe_quality(self, event: Event) -> None:
        if self._quality.clipped(self._settings.audio_clip_fraction):
            previous = self._session.audio_quality
            self._session.note_audio_quality(AudioQuality.CLIPPED)
            if previous is AudioQuality.OK:
                self._metrics.audio_clipped.inc()
        if not self._quality.silent(self._settings.audio_silence_rms):
            return
        if self._closed:
            return
        self._closed = True
        self._session.note_audio_quality(AudioQuality.DEAD)
        self._metrics.audio_dead.inc()
        end = self._session.create_event(
            EventKind.SESSION_END,
            {"reason": "audio_dead"},
            frame_index=event.frame_index,
        )
        _LOG.warning("audio_dead", session_id=self._session.session_id)
        if self._forward is not None:
            await self._forward(end)
