"""Abbreviation-safe first-chunk flush. Hold uses a fake clock, not wall sleep."""

import asyncio

from nlp.chunker import chunk_stream
from pipeline.event import EventKind
from pipeline.stages.chunker import ChunkerHandler
from server.config import Settings
from tests.conftest import Harness
from tests.support import counter_value

_ABBREVS = (
    "Dr. Khan can see you Wednesday at three p.m.",
    "Mr. Lee is in at 9 a.m.",
    "Mrs. Shah, Ms. Ortiz, and St. Mary clinic, e.g. walk-ins, i.e. today.",
)


def test_abbreviations_do_not_split() -> None:
    settings = Settings()
    for text in _ABBREVS:
        flushed, rest = chunk_stream(text, True, settings)
        spoken = " ".join([*flushed, rest]).strip()
        assert spoken == text
        for piece in flushed:
            assert piece not in {"Dr.", "Mr.", "Mrs.", "Ms.", "St.", "e.g.", "i.e.", "p.m.", "a.m."}


def test_dr_khan_first_chunk_stays_intact() -> None:
    settings = Settings()
    text = "Dr. Khan, your appointment is at 3 p.m."
    flushed, _rest = chunk_stream(text, True, settings)
    assert flushed
    assert flushed[0].startswith("Dr. Khan")
    assert "Dr." in flushed[0]


def test_four_word_comma_flushes_first_only() -> None:
    settings = Settings()
    text = "one two three four, five six seven eight nine ten"
    first, _rest = chunk_stream(text, True, settings)
    assert first == ["one two three four,"]
    later, leftover = chunk_stream(text, False, settings)
    assert later == []
    assert leftover == text


async def test_hold_flushes_twenty_words_on_fake_clock(harness: Harness) -> None:
    words = " ".join(f"word{i}" for i in range(20))
    clock = _FakeClock()
    emitted: list[str] = []

    async def forward(event: object) -> None:
        payload = getattr(event, "payload", {})
        emitted.append(str(payload.get("text") or ""))

    handler = ChunkerHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        forward=forward,
        clock=clock,
        sleep=clock.sleep,
    )
    event = harness.session.create_event(EventKind.SAY, {"text": words, "filler": 0})
    await handler(event)
    for _ in range(20):
        if emitted:
            break
        await asyncio.sleep(0)
    assert clock.now >= 0.4
    assert emitted
    assert "word0" in emitted[0]
    assert counter_value(harness.metrics.chunk_flush, reason="hold") == 1.0


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
