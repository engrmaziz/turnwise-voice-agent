"""Ring of recent bus frames so speech-start still has the onset."""

from __future__ import annotations

from collections import deque


class Preroll:
    """Last ``capacity`` frames, each 320 samples of PCM16."""

    __slots__ = ("_buf", "_capacity")

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("preroll capacity must be >= 1")
        self._capacity = capacity
        self._buf: deque[bytes] = deque(maxlen=capacity)

    def push(self, frame: bytes) -> None:
        self._buf.append(frame)

    def snapshot(self, triggering: bytes) -> bytes:
        """Pre-roll frames plus the frame that crossed into speech."""
        return b"".join(self._buf) + triggering

    def __len__(self) -> int:
        return len(self._buf)

    @property
    def capacity(self) -> int:
        return self._capacity

    def reset(self) -> None:
        self._buf.clear()
