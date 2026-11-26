"""Emotion timeout is None to fusion. Stale generation is dropped."""

import pytest

from models.emotion_pool import EmotionScorer
from nlp.fusion import EmotionProbs
from pipeline.event import EventKind
from pipeline.stages.emotion import EmotionHandler
from tests.conftest import Harness
from tests.support import counter_value


async def test_stub_returns_none() -> None:
    scorer = EmotionScorer.stub(timeout_ms=80)
    assert await scorer.score(b"\x00\x00", 0) is None
    scorer.close()


async def test_timeout_returns_none_and_counts(harness: Harness) -> None:
    scorer = EmotionScorer.stub(timeout_ms=20, sleep_s=0.2)
    handler = EmotionHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=scorer,
        metrics=harness.metrics,
    )
    event = harness.session.create_event(EventKind.TURN_END, {"reason": "test"})
    await handler(event)
    assert harness.session.last_emotion is None
    assert counter_value(harness.metrics.emotion_timeouts) == 1.0
    scorer.close()


async def test_stale_generation_is_dropped(harness: Harness) -> None:
    probs = EmotionProbs(calm=0.1, frustrated=0.8, distressed=0.1, generation=0)
    scorer = EmotionScorer.fixed(probs, timeout_ms=80)
    handler = EmotionHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=scorer,
        metrics=harness.metrics,
    )
    event = harness.session.create_event(EventKind.TURN_END, {"reason": "test"})
    harness.session.barge_in()
    await handler(event)
    assert harness.session.last_emotion is None
    scorer.close()


async def test_live_generation_is_kept(harness: Harness) -> None:
    probs = EmotionProbs(calm=0.2, frustrated=0.3, distressed=0.5, generation=0)
    scorer = EmotionScorer.fixed(probs, timeout_ms=80)
    handler = EmotionHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=scorer,
        metrics=harness.metrics,
    )
    harness.session.put_pcm(0, b"\x00\x00")
    event = harness.session.create_event(EventKind.TURN_END, {"reason": "test"})
    await handler(event)
    stored = harness.session.last_emotion
    assert stored is not None
    assert stored.distressed == pytest.approx(0.5)
    assert stored.generation == event.generation
    scorer.close()
