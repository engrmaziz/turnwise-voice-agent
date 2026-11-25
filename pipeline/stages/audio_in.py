"""Ingress stage. Rate is enforced at hello; this handler only accepts live audio."""

from pipeline.event import Event, EventKind


class AudioInHandler:
    """Counts live AUDIO events so tests can see ingest without a recognizer."""

    __slots__ = ("frames_accepted",)

    def __init__(self) -> None:
        self.frames_accepted = 0

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.AUDIO:
            return
        self.frames_accepted += 1
