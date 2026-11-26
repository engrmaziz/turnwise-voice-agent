"""Emit one event into several stage inboxes in order."""

from collections.abc import Awaitable, Callable

from pipeline.event import Event

Sink = Callable[[Event], Awaitable[None]]


def fan_out(*sinks: Sink) -> Sink:
    """Return a forward callable that awaits each sink in declaration order."""

    async def _emit(event: Event) -> None:
        for sink in sinks:
            await sink(event)

    return _emit
