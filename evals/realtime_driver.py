"""Wall-clock PCM WebSocket driver. Play-ack TTFA is scraped from the in-process histogram."""

from __future__ import annotations

import asyncio
import contextlib
import math
import socket
import struct
import wave
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import uvicorn
import websockets
from websockets.exceptions import ConnectionClosed

from evals.load import histogram_p95
from pipeline.audio.format import resample_mono_pcm16
from pipeline.metrics import StageMetrics
from server.app import create_app
from server.config import Settings
from server.transport import AudioHello, MsgType, encode_ack, encode_close, encode_hello, encode_pcm


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def utterance_frames(
    settings: Settings,
    *,
    speech_frames: int = 50,
    silence_frames: int = 50,
) -> list[bytes]:
    """Tone then silence so energy-VAD can start speech and the endpointer can fire."""
    samples = settings.ws_frame_samples
    rate = settings.ws_sample_rate_hz
    frames: list[bytes] = []
    for index in range(speech_frames):
        out: list[int] = []
        start = index * samples
        for i in range(samples):
            t = (start + i) / rate
            out.append(int(32767 * 0.2 * math.sin(2.0 * math.pi * 440.0 * t)))
        frames.append(struct.pack(f"<{samples}h", *out))
    quiet = struct.pack(f"<{samples}h", *([0] * samples))
    frames.extend([quiet] * silence_frames)
    return frames


def frames_from_wav(
    path: Path,
    settings: Settings,
    *,
    max_s: float = 2.0,
    silence_s: float = 1.0,
) -> list[bytes]:
    """Resample a mono fixture, cap duration, then append silence for the endpointer."""
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
            raise ValueError("wav must be mono PCM16")
        raw = wav.readframes(wav.getnframes())
        src_hz = wav.getframerate()
    pcm = resample_mono_pcm16(raw, src_hz, settings.ws_sample_rate_hz)
    cap = int(settings.ws_sample_rate_hz * max_s) * 2
    pcm = pcm[:cap]
    frame = settings.ws_pcm_bytes
    frames = [pcm[offset : offset + frame] for offset in range(0, len(pcm) - frame + 1, frame)]
    quiet = b"\x00" * frame
    silence_frames = max(1, int(silence_s * 1000 / settings.ws_frame_ms))
    frames.extend([quiet] * silence_frames)
    return frames


async def run_pcm_sessions(
    settings: Settings,
    *,
    n: int,
    pace_s: float,
    frames: Sequence[bytes] | None = None,
) -> dict[str, object]:
    """Start one in-process app, drive n sockets, scrape play-ack TTFA."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if pace_s < 0:
        raise ValueError("pace_s must be >= 0")
    app = create_app(settings)
    port = pick_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)
    serve = asyncio.create_task(server.serve(), name="realtime-uvicorn")
    try:
        await _wait_started(server)
        pcm = list(frames) if frames is not None else utterance_frames(settings)
        acked = 0
        for _ in range(n):
            if await _one_session(
                f"ws://127.0.0.1:{port}{settings.ws_path}",
                settings,
                pcm,
                pace_s,
                app.container.metrics,
            ):
                acked += 1
        samples, p95 = histogram_p95(app.container.metrics)
    finally:
        server.should_exit = True
        await asyncio.wait_for(serve, timeout=10.0)
        tts = app.container.tts_pool
        if tts is not None:
            tts.close()
        asr = app.container.asr_pool
        if asr is not None:
            asr.close()
        llm = app.container.llm_client
        if llm is not None:
            llm.close()
    tts_name = app.container.tts_pool.model_name if app.container.tts_pool is not None else "stub"
    path = "piper_play_ack" if tts_name.startswith("piper") else "stub_play_ack"
    return {
        "sessions_acked": acked,
        "ttfa_samples": samples,
        "ttfa_p95_s": p95,
        "ttfa_p95_source": "histogram_bucket",
        "ttfa_path": path,
        "tts_backend": tts_name,
        "product_quote": False,
    }


async def _one_session(
    url: str,
    settings: Settings,
    frames: Sequence[bytes],
    pace_s: float,
    metrics: StageMetrics,
) -> bool:
    hello = encode_hello(
        AudioHello(
            session_id=str(uuid4()),
            sample_rate_hz=settings.ws_sample_rate_hz,
            frame_samples=settings.ws_frame_samples,
            aec=True,
            ns=True,
        )
    )
    play_acks = 0
    before, _p95 = histogram_p95(metrics)
    got_ttfa = asyncio.Event()

    async def watch_ttfa() -> None:
        while True:
            samples, _ = histogram_p95(metrics)
            if samples > before:
                got_ttfa.set()
                return
            await asyncio.sleep(0.02)

    async with websockets.connect(url, open_timeout=5, close_timeout=5, max_size=2**22) as ws:

        async def receiver() -> None:
            nonlocal play_acks
            try:
                async for message in ws:
                    if not isinstance(message, bytes) or len(message) < 5:
                        continue
                    if message[0] != int(MsgType.PCM):
                        continue
                    frame_index = int.from_bytes(message[1:5], "little")
                    await ws.send(encode_ack(frame_index, "play"))
                    play_acks += 1
            except ConnectionClosed:
                return

        recv_task = asyncio.create_task(receiver())
        watch_task = asyncio.create_task(watch_ttfa())
        try:
            await ws.send(hello)
            for index, frame in enumerate(frames):
                await ws.send(encode_pcm(index, frame))
                if pace_s > 0:
                    await asyncio.sleep(pace_s)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(got_ttfa.wait(), timeout=15.0)
            with contextlib.suppress(ConnectionClosed):
                await ws.send(encode_close())
        finally:
            recv_task.cancel()
            watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionClosed):
                await recv_task
            with contextlib.suppress(asyncio.CancelledError):
                await watch_task
    return play_acks >= 1


async def _wait_started(server: uvicorn.Server) -> None:
    started = asyncio.Event()

    async def poll() -> None:
        while not server.started:  # noqa: ASYNC110 — uvicorn exposes started, not an Event
            await asyncio.sleep(0.02)
        started.set()

    poll_task = asyncio.create_task(poll())
    try:
        await asyncio.wait_for(started.wait(), timeout=15.0)
    except TimeoutError as exc:
        raise TimeoutError("uvicorn did not start") from exc
    finally:
        poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poll_task
