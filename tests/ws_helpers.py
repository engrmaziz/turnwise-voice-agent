"""Shared WebSocket client helpers for foundation tests."""

import math
import struct

from server.config import Settings
from server.transport import AudioHello, encode_hello, encode_pcm

SESSION_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def hello_bytes(
    session_id: str = SESSION_A,
    *,
    sample_rate_hz: int = 16000,
    frame_samples: int = 320,
    aec: bool = True,
    ns: bool = True,
) -> bytes:
    return encode_hello(
        AudioHello(
            session_id=session_id,
            sample_rate_hz=sample_rate_hz,
            frame_samples=frame_samples,
            aec=aec,
            ns=ns,
        )
    )


def tone_pcm(frame_index: int, *, samples: int = 320, rate: int = 16000) -> bytes:
    """440 Hz sine at 0.2 amplitude, 16-bit little-endian."""
    out: list[int] = []
    start = frame_index * samples
    for i in range(samples):
        t = (start + i) / rate
        out.append(int(32767 * 0.2 * math.sin(2.0 * math.pi * 440.0 * t)))
    return struct.pack(f"<{samples}h", *out)


def pcm_message(frame_index: int, settings: Settings | None = None) -> bytes:
    resolved = Settings() if settings is None else settings
    return encode_pcm(frame_index, tone_pcm(frame_index, samples=resolved.ws_frame_samples))
