"""Worker surfaces the benchmark times. Pools will implement these later."""

from typing import Protocol


class Benchmarkable(Protocol):
    """One timed call. The bench never sits on the call path."""

    def describe(self) -> str:
        """Version string as printed by the library or binary, not a guess."""

    def run_once(self) -> None:
        """One measured invocation. Must return or raise; it must not hang."""
