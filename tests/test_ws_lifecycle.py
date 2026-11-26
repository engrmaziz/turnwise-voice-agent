"""Session open/close on the audio WebSocket."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import create_app
from server.config import Settings
from server.transport import encode_close
from tests.ws_helpers import SESSION_A, hello_bytes, pcm_message, receive_until_disconnect


def test_session_is_gone_after_close(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        ws.send_bytes(encode_close())
    assert SESSION_A not in app.container.sessions
    assert len(app.container.sessions) == 0


def test_second_hello_is_rejected(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes())
        ws.send_bytes(hello_bytes(session_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
        with pytest.raises(WebSocketDisconnect):
            receive_until_disconnect(ws.receive_bytes)
    assert len(app.container.sessions) == 0


def test_pcm_before_hello_is_rejected(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(pcm_message(0, settings))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_bytes()
    assert len(app.container.sessions) == 0


def test_max_sessions(settings: Settings) -> None:
    capped = settings.model_copy(update={"ws_max_sessions": 1})
    app = create_app(capped)
    with TestClient(app) as client, client.websocket_connect(capped.ws_path) as first:
        first.send_bytes(hello_bytes())
        with client.websocket_connect(capped.ws_path) as second:
            second.send_bytes(hello_bytes(session_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
            with pytest.raises(WebSocketDisconnect):
                receive_until_disconnect(second.receive_bytes)
        first.send_bytes(encode_close())
    assert len(app.container.sessions) == 0
