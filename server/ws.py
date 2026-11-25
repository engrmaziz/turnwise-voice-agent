"""WebSocket audio endpoint. One LiveCall per socket, torn down on close."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import structlog
from fastapi import WebSocket
from opentelemetry.trace import Tracer, get_tracer
from starlette.websockets import WebSocketDisconnect, WebSocketState

from pipeline.errors import StageBackpressureError
from pipeline.event import EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session, SessionStore
from pipeline.stage import Stage, StageConfig
from pipeline.stages.audio_in import AudioInHandler
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
    parse_message,
)

_LOG = structlog.get_logger("server.ws")


class WsContainer(Protocol):
    settings: Settings
    metrics: StageMetrics
    sessions: SessionStore
    tracing: Tracing | None
    closed_snapshots: list[ClosedCallSnapshot] | None

    @property
    def make_audio_handler(self) -> Callable[[], AudioInHandler]: ...


@dataclass(slots=True)
class LiveCall:
    session: Session
    stage: Stage
    handler: AudioInHandler
    playback: PlaybackCursor
    next_frame_index: int


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
            parsed = parse_message(
                data,
                expected_pcm_bytes=settings.ws_pcm_bytes,
                expected_sample_rate_hz=settings.ws_sample_rate_hz,
                expected_frame_samples=settings.ws_frame_samples,
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
    session_id = parsed.hello.session_id.strip() or str(uuid.uuid4())
    session = container.sessions.open(session_id)
    handler = container.make_audio_handler()
    stage = Stage(
        name="audio_in",
        session_id=session.session_id,
        sessions=container.sessions,
        handler=handler,
        config=StageConfig(
            queue_maxsize=container.settings.stage_queue_maxsize,
            put_timeout_s=container.settings.stage_put_timeout_s,
        ),
        tracer=_tracer(container),
        metrics=container.metrics,
    )
    stage.start()
    container.metrics.ws_frames.labels(direction="in").inc()
    _LOG.info("ws_session_open", session_id=session.session_id, aec=parsed.hello.aec)
    return LiveCall(
        session=session,
        stage=stage,
        handler=handler,
        playback=PlaybackCursor(),
        next_frame_index=0,
    )


async def _on_pcm(container: WsContainer, call: LiveCall | None, parsed: PcmMessage) -> None:
    if call is None:
        raise ProtocolError("pcm_before_hello")
    if parsed.frame_index < call.next_frame_index:
        raise ProtocolError("frame_index_rewind")
    if parsed.frame_index > call.next_frame_index + 2:
        raise ProtocolError("frame_index_gap")
    if parsed.frame_index > call.next_frame_index:
        call.next_frame_index = parsed.frame_index
    event = call.session.create_event(
        EventKind.AUDIO,
        {"samples": container.settings.ws_frame_samples},
        frame_index=parsed.frame_index,
    )
    await call.stage.emit(event)
    call.next_frame_index = parsed.frame_index + 1
    container.metrics.ws_frames.labels(direction="in").inc()


def _on_ack(container: WsContainer, call: LiveCall | None, parsed: AckMessage) -> None:
    if call is None:
        raise ProtocolError("ack_before_hello")
    call.playback.ack(parsed.frame_index)
    container.metrics.ws_frames.labels(direction="in").inc()


async def _teardown(container: WsContainer, call: LiveCall | None) -> None:
    if call is None:
        return
    await call.stage.inbox.join()
    snapshots = container.closed_snapshots
    if snapshots is not None:
        snapshots.append(
            ClosedCallSnapshot(
                session_id=call.session.session_id,
                frames_accepted=call.handler.frames_accepted,
                acked_frame=call.playback.acked_frame,
            )
        )
    await call.stage.aclose()
    container.sessions.close(call.session.session_id)
    _LOG.info("ws_session_close", session_id=call.session.session_id)


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
