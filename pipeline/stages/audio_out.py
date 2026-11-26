"""Pack TTS PCM into play-stream frames and observe TTFA on play-ack."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import get_current_span

from models.tts_cache import TtsCache, cached_synthesize
from models.tts_pool import TtsError, TtsJob, TtsPool, TtsTimeoutError
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics, observe_ttfa
from pipeline.session import Session
from server.config import Settings
from server.playback import PlaybackCursor
from server.transport import encode_pcm

_LOG = structlog.get_logger("pipeline.stages.audio_out")

SendFn = Callable[[bytes], Awaitable[None]]


def pack_frames(pcm: bytes, frame_bytes: int) -> list[bytes]:
    if frame_bytes < 2 or frame_bytes % 2 != 0:
        raise ValueError("frame_bytes must be a positive even PCM size")
    if not pcm:
        raise TtsError("empty pcm")
    frames: list[bytes] = []
    for offset in range(0, len(pcm), frame_bytes):
        chunk = pcm[offset : offset + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk = chunk + b"\x00" * (frame_bytes - len(chunk))
        frames.append(chunk)
    return frames


class AudioOutHandler:
    """One instance per call. Play indexes start at 0 for each SAY generation."""

    __slots__ = (
        "_cache",
        "_filler_by_frame",
        "_metrics",
        "_play_index",
        "_playback",
        "_pool",
        "_saw_content",
        "_saw_ttfa",
        "_send",
        "_session",
        "_settings",
        "_ttfa_turn_end",
        "emitted",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        pool: TtsPool,
        cache: TtsCache,
        playback: PlaybackCursor,
        send: SendFn | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._pool = pool
        self._cache = cache
        self._playback = playback
        self._send = send
        self._play_index = 0
        self._filler_by_frame: dict[int, int] = {}
        self._saw_ttfa = False
        self._saw_content = False
        self._ttfa_turn_end: float | None = None
        self.emitted = 0

    def set_send(self, send: SendFn) -> None:
        self._send = send

    def note_play_ack(self, frame_index: int) -> None:
        """Called from the WebSocket thread when a play-stream ack arrives."""
        turn_end = self._session.turn_end_ts
        if turn_end is None:
            return
        if self._ttfa_turn_end != turn_end:
            self._ttfa_turn_end = turn_end
            self._saw_ttfa = False
            self._saw_content = False
        filler = self._filler_by_frame.get(frame_index, 1)
        self._saw_ttfa, self._saw_content = observe_ttfa(
            self._metrics,
            turn_end,
            time.monotonic(),
            filler=filler,
            saw_any=self._saw_ttfa,
            saw_content=self._saw_content,
        )

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.BARGE_IN:
            self._reset_play()
            return
        if event.kind is not EventKind.TTS_CHUNK:
            return
        span = get_current_span()
        started = time.perf_counter()
        job = TtsJob(
            session_id=event.session_id,
            generation=event.generation,
            text=str(event.payload.get("text") or ""),
            voice=str(event.payload.get("voice") or self._settings.tts_voice),
            speed=float(event.payload.get("speed") or self._settings.tts_speed),
            cache_key=str(event.payload.get("cache_key") or "") or None,
            filler=int(event.payload.get("filler") or 0),
            first_chunk=int(event.payload.get("first_chunk") or 0) == 1,
        )
        template_id = str(event.payload.get("template_id") or "")
        try:
            result = await cached_synthesize(
                self._cache,
                self._pool,
                job,
                live=lambda: self._session.generation,
                metrics=self._metrics,
                warmup_id=template_id,
            )
        except TtsTimeoutError:
            await self._fallback_cannot_speak(event.generation)
            return
        except TtsError:
            await self._fallback_cannot_speak(event.generation)
            return
        if result is None:
            return
        span.set_attribute("model", "tts")
        span.set_attribute("cache", "hit" if result.cache_hit else "miss")
        span.set_attribute("latency_ms", result.latency_ms)
        span.set_attribute("generation", event.generation)
        if result.cache_hit and result.latency_ms < 5:
            span.set_attribute("cache_fast", 1)
        frames = pack_frames(result.pcm, self._settings.tts_pcm_bytes)
        start = self._play_index
        for frame in frames:
            if self._session.generation != event.generation:
                return
            index = self._play_index
            self._filler_by_frame[index] = job.filler
            if self._send is not None:
                try:
                    await self._send(encode_pcm(index, frame))
                except Exception as exc:
                    if type(exc).__name__ not in {"WebSocketDisconnect", "WebSocketDisconnected"}:
                        raise
                    return
            self._play_index += 1
            self.emitted += 1
        end = self._play_index - 1
        if end >= start:
            self._playback.note_chunk(start, end, job.text)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        span.set_attribute("latency_ms", elapsed_ms)
        _LOG.info(
            "play_frames",
            session_id=self._session.session_id,
            frames=len(frames),
            cache="hit" if result.cache_hit else "miss",
        )

    async def _fallback_cannot_speak(self, generation: int) -> None:
        phrase = self._cache.lookup(
            "I am having trouble speaking. Please hold.",
            self._settings.tts_voice,
            self._settings.tts_speed,
        )
        if phrase is None:
            _LOG.warning("tts_unavailable", session_id=self._session.session_id)
            return
        if self._session.generation != generation:
            return
        frames = pack_frames(phrase, self._settings.tts_pcm_bytes)
        start = self._play_index
        for frame in frames:
            index = self._play_index
            self._filler_by_frame[index] = 0
            if self._send is not None:
                try:
                    await self._send(encode_pcm(index, frame))
                except Exception as exc:
                    if type(exc).__name__ not in {"WebSocketDisconnect", "WebSocketDisconnected"}:
                        raise
                    return
            self._play_index += 1
            self.emitted += 1
        end = self._play_index - 1
        if end >= start:
            self._playback.note_chunk(start, end, "cannot_speak")

    def _reset_play(self) -> None:
        self._play_index = 0
        self._filler_by_frame.clear()
        self._playback.reset()
