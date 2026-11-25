"""Immutable pipeline events. Payload stays off logs and span attributes."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

JsonValue = str | int | float | bool | None


class EventKind(StrEnum):
    """Coarse event types the bus routes. Voice stages are not implemented yet."""

    AUDIO = "audio"
    PARTIAL = "partial"
    FINAL = "final"
    TURN_END = "turn_end"
    NLU = "nlu"
    TOOL_RESULT = "tool_result"
    SAY = "say"
    TTS_CHUNK = "tts_chunk"
    BARGE_IN = "barge_in"
    SESSION_END = "session_end"


@dataclass(slots=True, frozen=True)
class Event:
    """One fact on the bus, stamped with the session clock at creation.

    ``session_id`` is an opaque id (a UUID), never a name or phone number.
    ``frame_index`` is the shared audio clock; non-audio events leave it unset.
    ``generation`` is the session generation at creation. Consumers compare it
    to the live session generation and drop mismatches.
    """

    kind: EventKind
    session_id: str
    turn_id: int
    generation: int
    frame_index: int | None
    payload: Mapping[str, JsonValue]
    ts_monotonic: float

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if self.turn_id < 0 or self.generation < 0:
            raise ValueError("turn_id and generation must be >= 0")
        if self.frame_index is not None and self.frame_index < 0:
            raise ValueError("frame_index must be >= 0")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
