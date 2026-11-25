"""Server frame clock. Client indexes must stay within two frames of expected."""

from __future__ import annotations


class ClockError(Exception):
    """A client frame_index the server will not follow. The socket closes."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class FrameClock:
    """Monotonic 20 ms index starting at 0 on session open.

    A jump of 1 or 2 frames is a gap we skip. A jump of 3 or more (for example
    0, 1, 4) is a broken stream. A rewind is also fatal.
    """

    __slots__ = ("_gaps", "_next_index")

    def __init__(self) -> None:
        self._next_index = 0
        self._gaps = 0

    @property
    def next_index(self) -> int:
        return self._next_index

    @property
    def gaps(self) -> int:
        return self._gaps

    def accept(self, frame_index: int) -> int:
        if frame_index < 0:
            raise ClockError("frame_index_negative")
        if frame_index < self._next_index:
            raise ClockError("frame_index_rewind")
        skipped = frame_index - self._next_index
        # 0,1,4 skips two expected indexes. Only a single missing frame is tolerated.
        if skipped > 1:
            raise ClockError("frame_index_gap")
        if skipped > 0:
            self._gaps += skipped
        self._next_index = frame_index + 1
        return frame_index
