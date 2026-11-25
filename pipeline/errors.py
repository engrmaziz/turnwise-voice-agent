"""Failures the stage runtime expects callers to handle."""


class StageBackpressureError(Exception):
    """The downstream inbox stayed full until ``stage_put_timeout_s`` elapsed."""

    def __init__(self, stage: str, timeout_s: float) -> None:
        self.stage = stage
        self.timeout_s = timeout_s
        super().__init__(f"stage {stage} inbox full after {timeout_s}s")


class SessionNotFoundError(Exception):
    """A stage looked up a session the store no longer holds."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"unknown session_id {session_id}")
