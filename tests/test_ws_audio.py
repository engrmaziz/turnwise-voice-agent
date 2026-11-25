"""Tone round trip: 50 sequential PCM frames and a play ack."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pipeline.event import Event, EventKind
from pipeline.stage import StageConfig
from pipeline.stages.audio_in import AudioInHandler
from server.app import create_app
from server.config import Settings
from server.playback import PlaybackCursor
from server.transport import encode_ack, encode_close, encode_pcm
from tests.conftest import Harness
from tests.support import counter_value
from tests.ws_helpers import SESSION_A, hello_bytes, pcm_message, tone_pcm


def test_fifty_tone_frames_and_play_ack(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        for index in range(50):
            ws.send_bytes(pcm_message(index, settings))
        ws.send_bytes(encode_ack(4))
        ws.send_bytes(encode_close())
    snapshot = app.container.closed_snapshots
    assert snapshot is not None
    assert len(snapshot) == 1
    closed = snapshot[0]
    assert closed.session_id == SESSION_A
    assert closed.frames_accepted == 50
    assert closed.acked_frame == 4
    assert SESSION_A not in app.container.sessions


def test_rewind_is_rejected(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        ws.send_bytes(pcm_message(0, settings))
        ws.send_bytes(pcm_message(0, settings))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_bytes()
    snapshot = app.container.closed_snapshots
    assert snapshot is not None
    assert snapshot[0].frames_accepted == 1


def test_wrong_pcm_length_increments_reject(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        ws.send_bytes(encode_pcm(0, b"\x00\x00"))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_bytes()
    assert counter_value(app.container.metrics.ws_rejects, reason="pcm_length") == 1.0


class _HoldHandler(AudioInHandler):
    """Keeps the first AUDIO event so the inbox can fill in the backpressure test."""

    def __init__(self) -> None:
        super().__init__()
        self.gate = asyncio.Event()

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.AUDIO:
            return
        await self.gate.wait()
        self.frames_accepted += 1


def test_inbox_full_closes_1011(settings: Settings) -> None:
    tight = settings.model_copy(update={"stage_queue_maxsize": 1, "stage_put_timeout_s": 0.05})
    app = create_app(tight)
    app.container.make_audio_handler = _HoldHandler
    with TestClient(app) as client, client.websocket_connect(tight.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        for index in range(4):
            ws.send_bytes(pcm_message(index, tight))
        with pytest.raises(WebSocketDisconnect) as disconnected:
            ws.receive_bytes()
    assert disconnected.value.code == 1011
    assert counter_value(app.container.metrics.ws_rejects, reason="backpressure") == 1.0


async def test_audio_in_drops_stale_after_barge_in(harness: Harness) -> None:
    seen: list[int] = []

    async def handler(event: Event) -> None:
        if event.kind is EventKind.AUDIO and event.frame_index is not None:
            seen.append(event.frame_index)

    stage = harness.stage(
        "audio_in", handler, config=StageConfig(queue_maxsize=8, put_timeout_s=0.25)
    )
    stage.start()
    live = harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=0)
    await stage.emit(live)
    for _ in range(20):
        if seen:
            break
        await asyncio.sleep(0)
    assert seen == [0]
    harness.session.barge_in()
    stale = harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=1)
    # create_event after barge_in stamps the new generation. Build a stale copy.
    stale_old = Event(
        kind=EventKind.AUDIO,
        session_id=live.session_id,
        turn_id=live.turn_id,
        generation=live.generation,
        frame_index=1,
        payload={"samples": 320},
        ts_monotonic=live.ts_monotonic,
    )
    await stage.emit(stale_old)
    await asyncio.sleep(0)
    assert seen == [0]
    await stage.emit(stale)
    for _ in range(20):
        if len(seen) == 2:
            break
        await asyncio.sleep(0)
    assert seen == [0, 1]
    await stage.aclose()


def test_playback_cursor_advances() -> None:
    cursor = PlaybackCursor()
    assert cursor.acked_frame == -1
    cursor.ack(4)
    assert cursor.acked_frame == 4
    cursor.ack(2)
    assert cursor.acked_frame == 4


def test_tone_pcm_is_640_bytes() -> None:
    assert len(tone_pcm(0)) == 640
