"""WebSocket audio endpoint. One LiveCall per socket, torn down on close."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog
from fastapi import WebSocket
from opentelemetry.trace import Tracer, get_tracer
from starlette.websockets import WebSocketDisconnect, WebSocketState

from models.asr_pool import AsrPool
from models.llm_client import LlmClient
from models.nlu_pool import NluScorer
from models.onnx_pool import TurnScorer
from models.tts_cache import TtsCache
from models.tts_pool import TtsPool
from models.vad_pool import VadEngine
from pipeline.audio.clock import ClockError, FrameClock
from pipeline.errors import StageBackpressureError
from pipeline.event import EventKind
from pipeline.fanout import fan_out
from pipeline.metrics import StageMetrics
from pipeline.session import Session, SessionStore
from pipeline.stage import Stage, StageConfig
from pipeline.stages.asr import AsrHandler
from pipeline.stages.audio_in import AudioInHandler
from pipeline.stages.audio_out import AudioOutHandler
from pipeline.stages.barge import BargeHandler
from pipeline.stages.chunker import ChunkerHandler
from pipeline.stages.dialogue import DialogueHandler
from pipeline.stages.endpoint import EndpointHandler
from pipeline.stages.nlu import NluHandler
from pipeline.stages.tts_norm import TtsNormHandler
from pipeline.stages.vad import VadHandler
from server.config import Settings
from server.playback import ClosedCallSnapshot, PlaybackCursor
from server.telemetry import Tracing
from server.transport import (
    CLOSE_INTERNAL,
    CLOSE_PROTOCOL,
    CLOSE_TRY_AGAIN,
    AckMessage,
    CloseMessage,
    HelloMessage,
    PcmMessage,
    ProtocolError,
    encode_pcm,
    parse_message,
)

_LOG = structlog.get_logger("server.ws")


class WsContainer(Protocol):
    settings: Settings
    metrics: StageMetrics
    sessions: SessionStore
    tracing: Tracing | None
    closed_snapshots: list[ClosedCallSnapshot] | None
    vad_engine: VadEngine
    asr_pool: AsrPool | None
    turn_scorer: TurnScorer | None
    nlu_scorer: NluScorer | None
    llm_client: LlmClient | None
    tts_pool: TtsPool | None
    tts_cache: TtsCache | None

    @property
    def make_audio_handler(self) -> Callable[[], AudioInHandler]: ...


@dataclass(slots=True)
class LiveCall:
    session: Session
    audio_stage: Stage
    vad_stage: Stage
    asr_stage: Stage
    endpoint_stage: Stage
    barge_stage: Stage
    nlu_stage: Stage
    dialogue_stage: Stage
    chunker_stage: Stage
    tts_norm_stage: Stage
    audio_out_stage: Stage
    handler: AudioInHandler
    vad_handler: VadHandler
    asr_handler: AsrHandler
    audio_out_handler: AudioOutHandler
    playback: PlaybackCursor
    clock: FrameClock
    pcm_bytes: int
    src_hz: int


async def handle_audio_socket(websocket: WebSocket, container: WsContainer) -> None:
    """Accept PCM16 frames after a hello. Always tears the session down on exit."""
    await websocket.accept()
    call: LiveCall | None = None
    settings = container.settings
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is None:
                container.metrics.ws_rejects.labels(reason="not_binary").inc()
                await _close(websocket, CLOSE_PROTOCOL)
                return
            if not isinstance(data, bytes):
                container.metrics.ws_rejects.labels(reason="not_binary").inc()
                await _close(websocket, CLOSE_PROTOCOL)
                return
            pcm_bytes = call.pcm_bytes if call is not None else settings.ws_pcm_bytes
            parsed = parse_message(
                data,
                expected_pcm_bytes=pcm_bytes,
                allowed_sample_rates=settings.allowed_sample_rates,
                frame_ms=settings.ws_frame_ms,
            )
            if isinstance(parsed, HelloMessage):
                call = await _on_hello(websocket, container, call, parsed)
            elif isinstance(parsed, PcmMessage):
                await _on_pcm(container, call, parsed)
            elif isinstance(parsed, AckMessage):
                _on_ack(container, call, parsed)
            elif isinstance(parsed, CloseMessage):
                await _close(websocket, 1000)
                return
    except ProtocolError as exc:
        container.metrics.ws_rejects.labels(reason=exc.reason).inc()
        _LOG.warning("ws_protocol_error", reason=exc.reason)
        await _close(websocket, exc.close_code)
    except StageBackpressureError:
        container.metrics.ws_rejects.labels(reason="backpressure").inc()
        await _close(websocket, CLOSE_INTERNAL)
    except WebSocketDisconnect:
        pass
    finally:
        await _teardown(container, call)


async def _on_hello(
    websocket: WebSocket,
    container: WsContainer,
    existing: LiveCall | None,
    parsed: HelloMessage,
) -> LiveCall:
    if existing is not None:
        raise ProtocolError("second_hello")
    if len(container.sessions) >= container.settings.ws_max_sessions:
        raise ProtocolError("max_sessions", CLOSE_TRY_AGAIN)
    settings = container.settings
    session_id = parsed.hello.session_id.strip() or str(uuid.uuid4())
    session = container.sessions.open(session_id)
    session.barge_in_enabled = parsed.hello.aec
    if not parsed.hello.aec:
        container.metrics.aec_disabled.inc()
        await _maybe_headphones_prompt(websocket, settings)
    config = StageConfig(
        queue_maxsize=settings.stage_queue_maxsize,
        put_timeout_s=settings.stage_put_timeout_s,
    )
    tracer = _tracer(container)
    pool = container.asr_pool
    if pool is None:
        pool = AsrPool.stub(settings, container.metrics)
    scorer = container.turn_scorer
    if scorer is None:
        scorer = TurnScorer.unavailable(timeout_ms=settings.turn_timeout_ms)
    playback = PlaybackCursor()
    asr_handler = AsrHandler(
        session=session,
        settings=settings,
        engine=pool,
        metrics=container.metrics,
    )
    asr_stage = Stage(
        name="asr",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=asr_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    endpoint_handler = EndpointHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        scorer=scorer,
    )
    endpoint_stage = Stage(
        name="endpoint",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=endpoint_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    barge_handler = BargeHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        playback=playback,
    )
    barge_stage = Stage(
        name="barge",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=barge_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    nlu = container.nlu_scorer
    if nlu is None:
        nlu = NluScorer.unavailable(timeout_ms=settings.nlu_timeout_ms)
    nlu_handler = NluHandler(
        session=session,
        settings=settings,
        scorer=nlu,
        metrics=container.metrics,
    )
    nlu_stage = Stage(
        name="nlu",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=nlu_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    llm = container.llm_client
    if llm is None:
        llm = LlmClient.unavailable(timeout_ms=settings.llm_timeout_ms)
    dialogue_handler = DialogueHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        llm=llm,
    )
    dialogue_stage = Stage(
        name="dialogue",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=dialogue_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    tts_pool = container.tts_pool
    if tts_pool is None:
        tts_pool = TtsPool.stub(
            timeout_ms=settings.tts_timeout_ms,
            frame_bytes=settings.tts_pcm_bytes,
        )
    tts_cache = container.tts_cache
    if tts_cache is None:
        tts_cache = TtsCache(warmup_ids=frozenset(settings.tts_warmup_list))
    audio_out_handler = AudioOutHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        pool=tts_pool,
        cache=tts_cache,
        playback=playback,
        send=websocket.send_bytes,
    )
    audio_out_stage = Stage(
        name="audio_out",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=audio_out_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    tts_norm_handler = TtsNormHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        forward=audio_out_stage.emit,
    )
    tts_norm_stage = Stage(
        name="tts_norm",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=tts_norm_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    chunker_handler = ChunkerHandler(
        session=session,
        settings=settings,
        metrics=container.metrics,
        forward=tts_norm_stage.emit,
    )
    chunker_stage = Stage(
        name="chunker",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=chunker_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    dialogue_handler.set_forward(chunker_stage.emit)
    nlu_handler.set_forward(dialogue_stage.emit)
    barge_handler.set_forward(fan_out(chunker_stage.emit, audio_out_stage.emit))
    asr_handler.set_forward(fan_out(endpoint_stage.emit, barge_stage.emit, nlu_stage.emit))
    endpoint_handler.set_forward(fan_out(asr_stage.emit, barge_stage.emit))
    vad_handler = VadHandler(
        session=session,
        settings=settings,
        engine=container.vad_engine,
        metrics=container.metrics,
        forward=fan_out(asr_stage.emit, endpoint_stage.emit, barge_stage.emit),
    )
    vad_stage = Stage(
        name="vad",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=vad_handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    override = container.make_audio_handler()
    if type(override) is AudioInHandler:
        handler = AudioInHandler(
            session=session,
            src_hz=parsed.hello.sample_rate_hz,
            dst_hz=settings.ws_sample_rate_hz,
            metrics=container.metrics,
            forward=vad_stage.emit,
        )
    else:
        handler = override
    audio_stage = Stage(
        name="audio_in",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=handler,
        config=config,
        tracer=tracer,
        metrics=container.metrics,
    )
    audio_out_stage.start()
    tts_norm_stage.start()
    chunker_stage.start()
    dialogue_stage.start()
    nlu_stage.start()
    asr_stage.start()
    endpoint_stage.start()
    barge_stage.start()
    vad_stage.start()
    audio_stage.start()
    await dialogue_handler.start()
    container.metrics.ws_frames.labels(direction="in").inc()
    _LOG.info(
        "ws_session_open",
        session_id=session.session_id,
        aec=parsed.hello.aec,
        sample_rate_hz=parsed.hello.sample_rate_hz,
        barge_in_enabled=session.barge_in_enabled,
    )
    return LiveCall(
        session=session,
        audio_stage=audio_stage,
        vad_stage=vad_stage,
        asr_stage=asr_stage,
        endpoint_stage=endpoint_stage,
        barge_stage=barge_stage,
        nlu_stage=nlu_stage,
        dialogue_stage=dialogue_stage,
        chunker_stage=chunker_stage,
        tts_norm_stage=tts_norm_stage,
        audio_out_stage=audio_out_stage,
        handler=handler,
        vad_handler=vad_handler,
        asr_handler=asr_handler,
        audio_out_handler=audio_out_handler,
        playback=playback,
        clock=FrameClock(),
        pcm_bytes=parsed.hello.frame_samples * 2,
        src_hz=parsed.hello.sample_rate_hz,
    )


async def _on_pcm(container: WsContainer, call: LiveCall | None, parsed: PcmMessage) -> None:
    if call is None:
        raise ProtocolError("pcm_before_hello")
    try:
        gaps_before = call.clock.gaps
        call.clock.accept(parsed.frame_index)
        if call.clock.gaps > gaps_before:
            container.metrics.clock_gaps.inc()
    except ClockError as exc:
        raise ProtocolError(exc.reason) from exc
    call.session.stage_wire_pcm(parsed.frame_index, parsed.pcm16)
    event = call.session.create_event(
        EventKind.AUDIO,
        {"samples": container.settings.ws_frame_samples},
        frame_index=parsed.frame_index,
    )
    await call.audio_stage.emit(event)
    container.metrics.ws_frames.labels(direction="in").inc()


def _on_ack(container: WsContainer, call: LiveCall | None, parsed: AckMessage) -> None:
    if call is None:
        raise ProtocolError("ack_before_hello")
    if parsed.stream != "play":
        container.metrics.play_ack_wrong_stream.inc()
        container.metrics.ws_frames.labels(direction="in").inc()
        return
    if not call.playback.ack(parsed.frame_index):
        container.metrics.playback_ack_ahead.inc()
        container.metrics.ws_frames.labels(direction="in").inc()
        return
    call.audio_out_handler.note_play_ack(parsed.frame_index)
    prefix = call.playback.prefix_for_ack(parsed.frame_index)
    if prefix:
        call.session.played_text = prefix
    container.metrics.ws_frames.labels(direction="in").inc()


def _read_headphones_pcm(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    pcm = path.read_bytes()
    if len(pcm) % 2 != 0:
        return b""
    return pcm


async def _maybe_headphones_prompt(websocket: WebSocket, settings: Settings) -> None:
    path = Path(settings.headphones_pcm_path)
    pcm = await asyncio.to_thread(_read_headphones_pcm, path)
    if pcm is None:
        _LOG.warning("prompt_missing", prompt="headphones_required", path=str(path))
        return
    if pcm == b"":
        _LOG.warning("prompt_missing", prompt="headphones_required", reason="odd_pcm")
        return
    frame = settings.ws_pcm_bytes
    index = 0
    offset = 0
    while offset + frame <= len(pcm):
        chunk = pcm[offset : offset + frame]
        await websocket.send_bytes(encode_pcm(index, chunk))
        offset += frame
        index += 1
    _LOG.info("headphones_prompt_queued", frames=index)


async def _teardown(container: WsContainer, call: LiveCall | None) -> None:
    if call is None:
        return
    pending: BaseException | None = None
    try:
        await asyncio.wait_for(call.audio_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.vad_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.asr_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.endpoint_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.barge_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.nlu_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.dialogue_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.chunker_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.tts_norm_stage.inbox.join(), timeout=2.0)
        await asyncio.wait_for(call.audio_out_stage.inbox.join(), timeout=2.0)
    except TimeoutError:
        _LOG.warning("ws_teardown_join_timeout", session_id=call.session.session_id)
    except asyncio.CancelledError as exc:
        pending = exc
        _LOG.warning("ws_teardown_join_cancelled", session_id=call.session.session_id)
    snapshots = container.closed_snapshots
    if snapshots is not None:
        snapshots.append(
            ClosedCallSnapshot(
                session_id=call.session.session_id,
                frames_accepted=call.handler.frames_accepted,
                acked_frame=call.playback.acked_frame,
            )
        )
    for stage in (
        call.audio_stage,
        call.vad_stage,
        call.asr_stage,
        call.endpoint_stage,
        call.barge_stage,
        call.nlu_stage,
        call.dialogue_stage,
        call.chunker_stage,
        call.tts_norm_stage,
        call.audio_out_stage,
    ):
        try:
            await stage.aclose()
        except asyncio.CancelledError as exc:
            pending = exc
            _LOG.warning("ws_teardown_aclose_cancelled", stage=stage.name)
    container.sessions.close(call.session.session_id)
    _LOG.info("ws_session_close", session_id=call.session.session_id)
    if pending is not None:
        raise pending


async def _close(websocket: WebSocket, code: int) -> None:
    if websocket.client_state is WebSocketState.CONNECTED:
        try:
            await websocket.close(code=code)
        except Exception as exc:
            # Starlette raises WebSocketDisconnect or WebSocketDisconnected
            # once a close frame is already in flight.
            if type(exc).__name__ not in {"WebSocketDisconnect", "WebSocketDisconnected"}:
                raise
            return


def _tracer(container: WsContainer) -> Tracer:
    tracing = container.tracing
    if tracing is None:
        return get_tracer("turnwise")
    return tracing.tracer
