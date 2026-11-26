"""Client play-ack cursor and linear frame-to-text prefix until TTS tags chunks."""

from dataclasses import dataclass


@dataclass(slots=True)
class ClosedCallSnapshot:
    """Last closed socket. Tests read frames and play-acks after teardown."""

    session_id: str
    frames_accepted: int
    acked_frame: int


@dataclass(frozen=True, slots=True)
class _Chunk:
    start_frame: int
    end_frame: int
    text: str


class PlaybackCursor:
    """Highest play-stream frame the client has queued to the device.

    Starts at -1 so frame 0 is a real first ack. Acks that go backwards are
    ignored. An ack ahead of any sent chunk is ignored and counted by the
    caller. ``note_chunk`` is what phase 7's TTS stage will call.
    """

    __slots__ = ("_chunks", "_sent_max", "acked_frame")

    def __init__(self) -> None:
        self.acked_frame = -1
        self._sent_max = -1
        self._chunks: list[_Chunk] = []

    @property
    def has_chunks(self) -> bool:
        return bool(self._chunks)

    def note_chunk(self, start_frame: int, end_frame: int, text: str) -> None:
        if start_frame < 0 or end_frame < start_frame:
            raise ValueError("chunk frame range is invalid")
        self._chunks.append(_Chunk(start_frame=start_frame, end_frame=end_frame, text=text))
        if end_frame > self._sent_max:
            self._sent_max = end_frame

    def ack(self, frame_index: int) -> bool:
        """Apply a play ack. False when the index is ahead of sent audio."""
        if frame_index < 0:
            raise ValueError("frame_index must be >= 0")
        if self._chunks and frame_index > self._sent_max:
            return False
        if frame_index > self.acked_frame:
            self.acked_frame = frame_index
        return True

    def prefix_for_ack(self, acked_frame: int) -> str:
        """Text whose frames are at or before ``acked_frame``. Empty if unmapped."""
        if acked_frame < 0 or not self._chunks:
            return ""
        parts: list[str] = []
        for chunk in self._chunks:
            if acked_frame < chunk.start_frame:
                break
            span = chunk.end_frame - chunk.start_frame + 1
            if acked_frame >= chunk.end_frame:
                parts.append(chunk.text)
                continue
            take = acked_frame - chunk.start_frame + 1
            chars = int(len(chunk.text) * take / span)
            parts.append(chunk.text[:chars])
            break
        return "".join(parts)
