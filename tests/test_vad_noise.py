"""Noise fixture starts less often than a counted speech fixture. License: generated."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

from models.vad_pool import VadInference
from pipeline.event import EventKind
from pipeline.stages.vad import VadHandler
from tests.conftest import Harness

# Generated white noise. Not MUSAN. Documented so a later MUSAN row can replace it.
NOISE_LICENSE = "generated-white-noise"


def _frame(amp: float, samples: int = 320, phase: int = 0) -> bytes:
    out = [
        int(32767 * amp * math.sin(2.0 * math.pi * 440.0 * (phase + i) / 16000))
        for i in range(samples)
    ]
    return struct.pack(f"<{samples}h", *out)


def _noise_frame(amp: float, seed: int, samples: int = 320) -> bytes:
    out: list[int] = []
    value = seed & 0xFFFFFFFF
    for _ in range(samples):
        value = (1103515245 * value + 12345) & 0x7FFFFFFF
        centered = (value / 0x7FFFFFFF) * 2.0 - 1.0
        out.append(int(32767 * amp * centered))
    return struct.pack(f"<{samples}h", *out)


@dataclass(slots=True)
class RmsVad:
    """Deterministic stand-in: probability tracks RMS. Used when ONNX is absent."""

    available: bool = True
    model_name: str = "rms-stub"
    opset: int | None = None
    calls: int = 0
    delay_s: float = 0.0
    generations: list[int] = field(default_factory=list)

    def new_state(self) -> object:
        return None

    async def infer(self, pcm16: bytes, state: object, generation: int) -> VadInference:
        import asyncio

        from pipeline.audio.quality import rms_full_scale

        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        self.calls += 1
        self.generations.append(generation)
        rms = rms_full_scale(pcm16)
        return VadInference(probability=min(1.0, rms / 0.05), state=state, generation=generation)

    def close(self) -> None:
        return


async def _run_fixture(harness: Harness, frames: list[bytes], engine: RmsVad) -> int:
    settings = harness.settings
    handler = VadHandler(
        session=harness.session,
        settings=settings,
        engine=engine,
        metrics=harness.metrics,
    )
    for index, pcm in enumerate(frames):
        harness.session.put_pcm(index, pcm)
        event = harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        await handler(event)
    return handler.speech_starts


async def test_noise_starts_less_than_speech(harness: Harness) -> None:
    speech = [_frame(0.0) for _ in range(25)] + [_frame(0.25, phase=i * 320) for i in range(40)]
    noise = [_noise_frame(0.008, seed=i) for i in range(65)]
    speech_starts = await _run_fixture(harness, speech, RmsVad())
    harness.session.barge_in()
    noise_starts = await _run_fixture(harness, noise, RmsVad())
    test_noise_starts_less_than_speech.counts = {  # type: ignore[attr-defined]
        "speech": speech_starts,
        "noise": noise_starts,
        "license": NOISE_LICENSE,
    }
    assert speech_starts >= 1
    assert noise_starts < speech_starts


class TimeoutVad:
    available = True
    model_name = "timeout"
    opset: int | None = None

    def new_state(self) -> object:
        return None

    async def infer(self, pcm16: bytes, state: object, generation: int) -> VadInference:
        raise TimeoutError

    def close(self) -> None:
        return


async def test_timeout_twice_uses_energy_gate(harness: Harness) -> None:
    handler = VadHandler(
        session=harness.session,
        settings=harness.settings,
        engine=TimeoutVad(),
        metrics=harness.metrics,
    )
    for index in range(4):
        harness.session.put_pcm(index, _frame(0.3, phase=index * 320))
        event = harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        await handler(event)
    from tests.support import counter_value

    assert counter_value(harness.metrics.vad_fallback) >= 1.0
