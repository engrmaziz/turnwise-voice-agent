"""Frame clock rejects a gap larger than two frames."""

import pytest

from pipeline.audio.clock import ClockError, FrameClock


def test_accepts_in_order() -> None:
    clock = FrameClock()
    assert clock.accept(0) == 0
    assert clock.accept(1) == 1
    assert clock.next_index == 2
    assert clock.gaps == 0


def test_allows_skip_of_one() -> None:
    clock = FrameClock()
    clock.accept(0)
    clock.accept(1)
    clock.accept(3)
    assert clock.gaps == 1
    assert clock.next_index == 4


def test_closes_on_index_0_1_4() -> None:
    clock = FrameClock()
    clock.accept(0)
    clock.accept(1)
    with pytest.raises(ClockError, match="frame_index_gap"):
        clock.accept(4)


def test_rewind_is_fatal() -> None:
    clock = FrameClock()
    clock.accept(0)
    with pytest.raises(ClockError, match="frame_index_rewind"):
        clock.accept(0)
