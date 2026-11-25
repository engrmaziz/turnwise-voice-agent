"""One high-probability frame does not start speech. 200 ms at 0.6 does."""

from pipeline.audio.vad_gate import VadGateConfig, VadMode, VadTracker, vad_decision
from server.config import Settings


def _config() -> VadGateConfig:
    settings = Settings()
    return VadGateConfig(
        threshold=settings.vad_speech_threshold,
        start_ms=settings.vad_speech_start_ms,
        max_utterance_ms=settings.vad_max_utterance_ms,
        frame_ms=settings.ws_frame_ms,
    )


def test_one_frame_at_0_99_does_not_start() -> None:
    tracker = VadTracker()
    step = vad_decision(0.99, tracker, _config())
    assert step.speech_started is False
    assert step.tracker.mode is VadMode.IDLE


def test_200ms_at_0_6_starts() -> None:
    tracker = VadTracker()
    started = False
    config = _config()
    frames = config.start_ms // config.frame_ms
    for _ in range(frames):
        step = vad_decision(0.6, tracker, config)
        tracker = step.tracker
        started = started or step.speech_started
    assert started is True
    assert tracker.mode is VadMode.IN_SPEECH


def test_hang_forces_idle() -> None:
    config = VadGateConfig(threshold=0.5, start_ms=20, max_utterance_ms=40, frame_ms=20)
    tracker = VadTracker()
    step = vad_decision(0.9, tracker, config)
    assert step.speech_started is True
    step = vad_decision(0.9, step.tracker, config)
    assert step.hang is False
    step = vad_decision(0.9, step.tracker, config)
    assert step.hang is True
    assert step.tracker.mode is VadMode.IDLE
