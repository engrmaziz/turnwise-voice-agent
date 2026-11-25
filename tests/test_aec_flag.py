"""Barge-in is gated on the hello AEC flag."""

from fastapi.testclient import TestClient

from pipeline.session import Session
from server.app import create_app
from server.config import Settings
from tests.ws_helpers import SESSION_A, hello_bytes


def test_request_barge_in_respects_flag() -> None:
    session = Session("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    session.barge_in_enabled = False
    generation = session.generation
    assert session.request_barge_in() is False
    assert session.generation == generation
    session.barge_in_enabled = True
    assert session.request_barge_in() is True
    assert session.generation == generation + 1


def test_hello_aec_false_disables_barge_in(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client, client.websocket_connect(settings.ws_path) as ws:
        ws.send_bytes(hello_bytes(aec=False, ns=True))
        session = app.container.sessions.get(SESSION_A)
        assert session.barge_in_enabled is False
        assert session.request_barge_in() is False
