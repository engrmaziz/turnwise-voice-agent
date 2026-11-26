"""LocalAgreement-2: commit the prefix two consecutive hypotheses share."""

from __future__ import annotations


def local_agreement_2(first: str, second: str) -> str:
    """Word-wise longest common prefix. Empty if the first words differ."""
    left = first.split()
    right = second.split()
    shared = 0
    limit = min(len(left), len(right))
    while shared < limit and left[shared] == right[shared]:
        shared += 1
    return " ".join(left[:shared])


class LocalAgreement2:
    """Stateful LA-2. The first hypothesis commits nothing."""

    __slots__ = ("_prev",)

    def __init__(self) -> None:
        self._prev: str | None = None

    def push(self, hypothesis: str) -> str:
        """Return the newly stable prefix, with a trailing space when non-empty."""
        if self._prev is None:
            self._prev = hypothesis
            return ""
        shared = local_agreement_2(self._prev, hypothesis)
        self._prev = hypothesis
        if not shared:
            return ""
        return f"{shared} "

    def reset(self) -> None:
        self._prev = None
