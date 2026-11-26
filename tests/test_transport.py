"""Binary protocol parser. One WebSocket message is one protocol message."""

import pytest

from server.config import Settings
from server.transport import (
    AckMessage,
    AudioHello,
    HelloMessage,
    ParsedMessage,
    ProtocolError,
    encode_ack,
    encode_close,
    encode_hello,
    encode_pcm,
    parse_message,
)


def _settings() -> Settings:
    return Settings()


def _parse(data: bytes) -> ParsedMessage:
    settings = _settings()
    return parse_message(
        data,
        expected_pcm_bytes=settings.ws_pcm_bytes,
        allowed_sample_rates=settings.allowed_sample_rates,
        frame_ms=settings.ws_frame_ms,
    )


def test_hello_round_trip() -> None:
    hello = AudioHello(
        session_id="11111111-1111-4111-8111-111111111111",
        sample_rate_hz=16000,
        frame_samples=320,
        aec=True,
        ns=True,
    )
    parsed = _parse(encode_hello(hello))
    assert isinstance(parsed, HelloMessage)
    assert parsed.hello == hello


def test_rejects_wrong_sample_rate() -> None:
    hello = AudioHello(
        session_id="s",
        sample_rate_hz=16000,
        frame_samples=320,
        aec=False,
        ns=False,
    )
    raw = encode_hello(hello).replace(b"16000", b"44100")
    with pytest.raises(ProtocolError, match=r"hello_json|sample_rate"):
        _parse(raw)


def test_accepts_8k_hello() -> None:
    hello = AudioHello(
        session_id="s",
        sample_rate_hz=8000,
        frame_samples=160,
        aec=True,
        ns=True,
    )
    parsed = _parse(encode_hello(hello))
    assert isinstance(parsed, HelloMessage)
    assert parsed.hello.sample_rate_hz == 8000


def test_rejects_pcm_length_not_640() -> None:
    with pytest.raises(ProtocolError, match="pcm_length"):
        _parse(encode_pcm(0, b"\x00\x00"))


def test_rejects_empty_and_unknown_type() -> None:
    with pytest.raises(ProtocolError, match="empty_frame"):
        _parse(b"")
    with pytest.raises(ProtocolError, match="unknown_type"):
        _parse(b"\x99")


def test_ack_and_close() -> None:
    ack = _parse(encode_ack(4))
    assert isinstance(ack, AckMessage)
    assert ack.frame_index == 4
    assert ack.stream == "play"
    cap = _parse(encode_ack(4, stream="cap"))
    assert isinstance(cap, AckMessage)
    assert cap.stream == "cap"
    _parse(encode_close())
    with pytest.raises(ProtocolError, match="close_trailing_bytes"):
        _parse(encode_close() + b"\x00")


def test_legacy_four_byte_ack_is_missing_stream() -> None:
    raw = bytes([0x03]) + (4).to_bytes(4, "little")
    with pytest.raises(ProtocolError, match="ack_missing_stream"):
        _parse(raw)
