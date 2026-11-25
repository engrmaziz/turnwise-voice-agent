"""Client play-ack cursor. Capture frame indexes are a different clock."""

from dataclasses import dataclass


@dataclass(slots=True)
class ClosedCallSnapshot:
    """Last closed socket. Tests read frames and play-acks after teardown."""

    session_id: str
    frames_accepted: int
    acked_frame: int


class PlaybackCursor:
    """Highest play-stream frame the client has queued to the device.

    Starts at -1 so frame 0 is a real first ack. Acks that go backwards are
    ignored; an ack ahead of any sent frame is counted by the caller.
    """

    __slots__ = ("acked_frame",)

    def __init__(self) -> None:
        self.acked_frame = -1

    def ack(self, frame_index: int) -> None:
        if frame_index < 0:
            raise ValueError("frame_index must be >= 0")
        if frame_index > self.acked_frame:
            self.acked_frame = frame_index
