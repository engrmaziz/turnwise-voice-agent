"""Binary WebSocket frames. One WebSocket message is one protocol message.

Byte 0 is the type. Hello is the only JSON. PCM is never base64.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum

from pydantic import BaseModel, Field, ValidationError

CLOSE_PROTOCOL = 1003
CLOSE_INTERNAL = 1011
CLOSE_TRY_AGAIN = 1013


class MsgType(IntEnum):
    HELLO = 0x01
    PCM = 0x02
    ACK = 0x03
    CLOSE = 0x04


class ProtocolError(Exception):
    """A frame the peer must not send. The socket closes with ``close_code``."""

    def __init__(self, reason: str, close_code: int = CLOSE_PROTOCOL) -> None:
        self.reason = reason
        self.close_code = close_code
        super().__init__(reason)


class AudioHello(BaseModel):
    session_id: str = Field(min_length=1)
    sample_rate_hz: int
    frame_samples: int
    aec: bool
    ns: bool


@dataclass(slots=True, frozen=True)
class HelloMessage:
    hello: AudioHello


@dataclass(slots=True, frozen=True)
class PcmMessage:
    frame_index: int
    pcm16: bytes


@dataclass(slots=True, frozen=True)
class AckMessage:
    frame_index: int


@dataclass(slots=True, frozen=True)
class CloseMessage:
    pass


ParsedMessage = HelloMessage | PcmMessage | AckMessage | CloseMessage


def parse_message(
    data: bytes,
    *,
    expected_pcm_bytes: int,
    expected_sample_rate_hz: int,
    expected_frame_samples: int,
) -> ParsedMessage:
    """Decode one binary WebSocket payload. Incomplete or extra bytes are errors."""
    if not data:
        raise ProtocolError("empty_frame")
    kind = data[0]
    if kind == MsgType.HELLO:
        return HelloMessage(
            hello=_parse_hello(data[1:], expected_sample_rate_hz, expected_frame_samples)
        )
    if kind == MsgType.PCM:
        return _parse_pcm(data[1:], expected_pcm_bytes)
    if kind == MsgType.ACK:
        return _parse_ack(data[1:])
    if kind == MsgType.CLOSE:
        if len(data) != 1:
            raise ProtocolError("close_trailing_bytes")
        return CloseMessage()
    raise ProtocolError("unknown_type")


def encode_hello(hello: AudioHello) -> bytes:
    payload = hello.model_dump_json().encode("utf-8")
    return bytes([MsgType.HELLO]) + len(payload).to_bytes(4, "little") + payload


def encode_pcm(frame_index: int, pcm16: bytes) -> bytes:
    if frame_index < 0:
        raise ValueError("frame_index must be >= 0")
    return bytes([MsgType.PCM]) + frame_index.to_bytes(4, "little") + pcm16


def encode_ack(frame_index: int) -> bytes:
    if frame_index < 0:
        raise ValueError("frame_index must be >= 0")
    return bytes([MsgType.ACK]) + frame_index.to_bytes(4, "little")


def encode_close() -> bytes:
    return bytes([MsgType.CLOSE])


def _parse_hello(body: bytes, sample_rate_hz: int, frame_samples: int) -> AudioHello:
    if len(body) < 4:
        raise ProtocolError("hello_truncated")
    length = int.from_bytes(body[:4], "little")
    raw = body[4:]
    if length != len(raw):
        raise ProtocolError("hello_length_mismatch")
    try:
        hello = AudioHello.model_validate(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ProtocolError("hello_json") from exc
    if hello.sample_rate_hz != sample_rate_hz:
        raise ProtocolError("sample_rate")
    if hello.frame_samples != frame_samples:
        raise ProtocolError("frame_samples")
    return hello


def _parse_pcm(body: bytes, expected_pcm_bytes: int) -> PcmMessage:
    if len(body) < 4:
        raise ProtocolError("pcm_truncated")
    frame_index = int.from_bytes(body[:4], "little")
    pcm16 = body[4:]
    if len(pcm16) != expected_pcm_bytes:
        raise ProtocolError("pcm_length")
    return PcmMessage(frame_index=frame_index, pcm16=pcm16)


def _parse_ack(body: bytes) -> AckMessage:
    if len(body) != 4:
        raise ProtocolError("ack_length")
    return AckMessage(frame_index=int.from_bytes(body, "little"))
