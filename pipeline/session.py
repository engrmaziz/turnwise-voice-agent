"""Per-call dialogue clock: turn, generation, and speaking-task cancellation."""

import asyncio
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from pipeline.errors import SessionNotFoundError
from pipeline.event import Event, EventKind, JsonValue


class AudioQuality(StrEnum):
    OK = "ok"
    CLIPPED = "clipped"
    DEAD = "dead"


_QUALITY_RANK = {AudioQuality.OK: 0, AudioQuality.CLIPPED: 1, AudioQuality.DEAD: 2}


class Session:
    """One phone call. Generation is the cancellation epoch for this call.

    ``barge_in`` increments generation and turn together, then cancels speaking
    tasks. There is no await between the increment and the cancels, so a task
    that resumes afterwards observes the new generation. The turn increment
    keeps the interrupted agent utterance and the caller's new speech in
    different traces.

    ``session_id`` must be an opaque id. Names, dates of birth, and phone
    numbers do not belong in it; logs and spans record it in the clear.
    """

    __slots__ = (
        "_audio_quality",
        "_barge_in_enabled",
        "_expected_vocab_id",
        "_generation",
        "_now",
        "_on_barge_in",
        "_pcm",
        "_session_id",
        "_speaking",
        "_timezone",
        "_turn_id",
        "_wire_pcm",
    )

    def __init__(
        self,
        session_id: str,
        *,
        on_barge_in: Callable[[], None] | None = None,
        now: datetime | None = None,
        timezone: ZoneInfo | None = None,
    ) -> None:
        if not session_id:
            raise ValueError("session_id must be non-empty")
        self._session_id = session_id
        self._turn_id = 0
        self._generation = 0
        self._speaking: set[asyncio.Task[None]] = set()
        self._on_barge_in = on_barge_in if on_barge_in is not None else _noop
        self._barge_in_enabled = True
        self._audio_quality = AudioQuality.OK
        self._pcm: dict[int, bytes] = {}
        self._wire_pcm: dict[int, bytes] = {}
        self._timezone = timezone if timezone is not None else ZoneInfo("America/New_York")
        if now is None:
            self._now = datetime.now(self._timezone)
        elif now.tzinfo is None:
            raise ValueError("session.now must be timezone-aware")
        else:
            self._now = now
        self._expected_vocab_id = "greet"

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def turn_id(self) -> int:
        return self._turn_id

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def speaking_task_count(self) -> int:
        return len(self._speaking)

    def is_stale(self, event: Event) -> bool:
        """True when the event is from another call or a superseded generation."""
        return event.session_id != self._session_id or event.generation != self._generation

    def next_turn(self) -> int:
        """Open a new turn without cancelling in-flight speech."""
        self._turn_id += 1
        return self._turn_id

    @property
    def barge_in_enabled(self) -> bool:
        return self._barge_in_enabled

    @barge_in_enabled.setter
    def barge_in_enabled(self, value: bool) -> None:
        self._barge_in_enabled = value

    @property
    def audio_quality(self) -> AudioQuality:
        return self._audio_quality

    def note_audio_quality(self, quality: AudioQuality) -> AudioQuality:
        """Keep the worst flag seen. ``dead`` outranks ``clipped`` outranks ``ok``."""
        if _QUALITY_RANK[quality] > _QUALITY_RANK[self._audio_quality]:
            self._audio_quality = quality
        return self._audio_quality

    @property
    def timezone(self) -> ZoneInfo:
        return self._timezone

    @property
    def now(self) -> datetime:
        return self._now

    @now.setter
    def now(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("session.now must be timezone-aware")
        self._now = value

    @property
    def expected_vocab_id(self) -> str:
        return self._expected_vocab_id

    @expected_vocab_id.setter
    def expected_vocab_id(self, value: str) -> None:
        if not value.strip():
            raise ValueError("expected_vocab_id must be non-empty")
        self._expected_vocab_id = value.strip()

    def request_barge_in(self) -> bool:
        """Run ``barge_in`` only when the client reported AEC on."""
        if not self._barge_in_enabled:
            return False
        self.barge_in()
        return True

    def barge_in(self) -> int:
        """Supersede the current generation and cancel registered speaking tasks."""
        self._generation += 1
        self._turn_id += 1
        self._pcm.clear()
        self._wire_pcm.clear()
        tasks = tuple(self._speaking)
        self._speaking.clear()
        for task in tasks:
            task.cancel()
        self._on_barge_in()
        return self._generation

    def stage_wire_pcm(self, frame_index: int, pcm: bytes) -> None:
        self._wire_pcm[frame_index] = pcm

    def take_wire_pcm(self, frame_index: int) -> bytes | None:
        return self._wire_pcm.pop(frame_index, None)

    def put_pcm(self, frame_index: int, pcm: bytes) -> None:
        self._pcm[frame_index] = pcm

    def get_pcm(self, frame_index: int) -> bytes | None:
        return self._pcm.get(frame_index)

    def track_speaking(self, task: asyncio.Task[None]) -> None:
        """Register a task that ``barge_in`` must cancel.

        Already-finished tasks are ignored so a late register cannot resurrect
        a done task into the speaking set.
        """
        if task.done():
            return
        self._speaking.add(task)
        task.add_done_callback(self._discard_speaking)

    def create_event(
        self,
        kind: EventKind,
        payload: Mapping[str, JsonValue] | None = None,
        *,
        frame_index: int | None = None,
    ) -> Event:
        """Stamp an event with this session's current turn and generation."""
        body: Mapping[str, JsonValue] = {} if payload is None else payload
        return Event(
            kind=kind,
            session_id=self._session_id,
            turn_id=self._turn_id,
            generation=self._generation,
            frame_index=frame_index,
            payload=body,
            ts_monotonic=time.monotonic(),
        )

    def _discard_speaking(self, task: asyncio.Task[None]) -> None:
        self._speaking.discard(task)


class SessionStore:
    """Sessions owned by one process. Constructed by the app and passed in."""

    __slots__ = ("_on_barge_in", "_sessions", "_timezone")

    def __init__(
        self,
        *,
        on_barge_in: Callable[[], None] | None = None,
        timezone: ZoneInfo | None = None,
    ) -> None:
        self._sessions: dict[str, Session] = {}
        self._on_barge_in = on_barge_in
        self._timezone = timezone

    def open(self, session_id: str) -> Session:
        if session_id in self._sessions:
            raise ValueError(f"session already open: {session_id}")
        session = Session(session_id, on_barge_in=self._on_barge_in, timezone=self._timezone)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(session_id) from exc

    def close(self, session_id: str) -> None:
        """Drop the session. Close its stages first; late events are then misrouted."""
        self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._sessions)

    def __contains__(self, session_id: object) -> bool:
        return isinstance(session_id, str) and session_id in self._sessions


def _noop() -> None:
    return
