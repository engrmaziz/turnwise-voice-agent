"""Dead-mic and clipping windows. Thresholds are passed in, not hardcoded."""

import struct

from models.vad_pool import VadPool
from pipeline.audio.quality import QualityWindow, clip_fraction, rms_full_scale
from pipeline.event import EventKind
from pipeline.session import AudioQuality
from pipeline.stages.vad import VadHandler
from tests.conftest import Harness


def _zeros(samples: int = 320) -> bytes:
    return b"\x00\x00" * samples


def _full_scale(samples: int = 320, peak: int = 32767) -> bytes:
    return struct.pack(f"<{samples}h", *([peak] * samples))


def _sine_frame(amp: float = 0.2, samples: int = 320) -> bytes:
    import math

    out = [int(32767 * amp * math.sin(2.0 * math.pi * 440.0 * i / 16000)) for i in range(samples)]
    return struct.pack(f"<{samples}h", *out)


def test_zeros_cross_silence_window() -> None:
    window = QualityWindow(frame_ms=20, window_s=3.0, clip_peak=32760)
    threshold = 0.005
    for _ in range(149):
        window.push(_zeros())
        assert window.silent(threshold) is False
    window.push(_zeros())
    assert window.silent(threshold) is True


def test_clip_fraction_two_percent() -> None:
    samples = 100
    peak = 32767
    values = [peak] * 2 + [0] * 98
    pcm = struct.pack(f"<{samples}h", *values)
    assert clip_fraction(pcm, 32760) == 0.02
    window = QualityWindow(frame_ms=20, window_s=0.02, clip_peak=32760)
    window.push(pcm)
    assert window.clipped(0.01) is True


def test_sine_rms_is_not_silent() -> None:
    assert rms_full_scale(_sine_frame()) > 0.005


async def test_dead_mic_emits_session_end_once(harness: Harness) -> None:
    settings = harness.settings.model_copy(update={"audio_silence_window_s": 0.1})
    ended: list[str] = []

    async def forward(event: object) -> None:
        kind = getattr(event, "kind", None)
        if kind is EventKind.SESSION_END:
            ended.append(str(getattr(event, "payload", {})))

    handler = VadHandler(
        session=harness.session,
        settings=settings,
        engine=VadPool.unavailable(timeout_ms=30),
        metrics=harness.metrics,
        forward=forward,
    )
    stage = harness.stage("vad", handler)
    stage.start()
    frames = int(0.1 * 1000 / settings.ws_frame_ms) + 2
    for index in range(frames * 2):
        harness.session.put_pcm(index, _zeros())
        await stage.emit(
            harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        )
    await stage.aclose()
    assert len(ended) == 1
    assert harness.session.audio_quality is AudioQuality.DEAD
    attrs = [span.attributes or {} for span in harness.exporter.get_finished_spans()]
    assert any(item.get("audio_quality") == "dead" for item in attrs)


async def test_sine_does_not_mark_dead(harness: Harness) -> None:
    settings = harness.settings.model_copy(update={"audio_silence_window_s": 0.1})
    handler = VadHandler(
        session=harness.session,
        settings=settings,
        engine=VadPool.unavailable(timeout_ms=30),
        metrics=harness.metrics,
    )
    for index in range(10):
        harness.session.put_pcm(index, _sine_frame())
        event = harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        await handler(event)
    assert harness.session.audio_quality is AudioQuality.OK
