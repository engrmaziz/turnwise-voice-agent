"""Linear frame-to-text prefix until TTS tags real chunks."""

from server.playback import PlaybackCursor
from tests.conftest import Harness
from tests.support import counter_value


def test_prefix_follows_acked_frames_not_the_full_string() -> None:
    cursor = PlaybackCursor()
    cursor.note_chunk(0, 9, "ABCDEFGHIJ")
    cursor.ack(3)
    # ack 3 covers frames 0-3 → 4 of 10 characters.
    assert cursor.prefix_for_ack(cursor.acked_frame) == "ABCD"
    assert cursor.prefix_for_ack(cursor.acked_frame) != "ABCDEFGHIJ"


def test_ack_ahead_of_sent_frames_is_ignored(harness: Harness) -> None:
    cursor = PlaybackCursor()
    cursor.note_chunk(0, 9, "ABCDEFGHIJ")
    cursor.ack(4)
    assert cursor.acked_frame == 4
    assert cursor.ack(99) is False
    assert cursor.acked_frame == 4
    harness.metrics.playback_ack_ahead.inc()
    assert counter_value(harness.metrics.playback_ack_ahead) == 1.0


def test_missing_map_is_empty_prefix() -> None:
    cursor = PlaybackCursor()
    cursor.ack(4)
    assert cursor.has_chunks is False
    assert cursor.prefix_for_ack(cursor.acked_frame) == ""
