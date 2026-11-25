"""Speech-start hysteresis. Endpointing in phase 4 owns leaving speech."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VadMode(StrEnum):
    IDLE = "idle"
    IN_SPEECH = "in_speech"


@dataclass(slots=True)
class VadTracker:
    mode: VadMode = VadMode.IDLE
    speech_ms: int = 0
    utterance_ms: int = 0


@dataclass(frozen=True, slots=True)
class VadGateConfig:
    threshold: float
    start_ms: int
    max_utterance_ms: int
    frame_ms: int


@dataclass(frozen=True, slots=True)
class VadStep:
    tracker: VadTracker
    speech_started: bool
    hang: bool


def vad_decision(prob: float, tracker: VadTracker, config: VadGateConfig) -> VadStep:
    """Enter speech after ``start_ms`` of frames at or above ``threshold``.

    A single high-probability frame does not start speech. Short silence after
    start does not leave ``in_speech``; only the hang timer does in this phase.
    """
    if config.frame_ms < 1:
        raise ValueError("frame_ms must be >= 1")
    if tracker.mode is VadMode.IN_SPEECH:
        utterance = tracker.utterance_ms + config.frame_ms
        hang = utterance >= config.max_utterance_ms
        if hang:
            return VadStep(
                tracker=VadTracker(mode=VadMode.IDLE, speech_ms=0, utterance_ms=0),
                speech_started=False,
                hang=True,
            )
        return VadStep(
            tracker=VadTracker(
                mode=VadMode.IN_SPEECH, speech_ms=tracker.speech_ms, utterance_ms=utterance
            ),
            speech_started=False,
            hang=False,
        )
    speech_ms = tracker.speech_ms + config.frame_ms if prob >= config.threshold else 0
    if speech_ms >= config.start_ms:
        return VadStep(
            tracker=VadTracker(mode=VadMode.IN_SPEECH, speech_ms=speech_ms, utterance_ms=0),
            speech_started=True,
            hang=False,
        )
    return VadStep(
        tracker=VadTracker(mode=VadMode.IDLE, speech_ms=speech_ms, utterance_ms=0),
        speech_started=False,
        hang=False,
    )
