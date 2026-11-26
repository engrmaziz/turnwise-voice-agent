"""Fusion arithmetic is locked to the starting weights. No fudge to cross 0.65."""

import pytest
from pydantic import ValidationError

from nlp.fusion import EmotionProbs, fuse
from pipeline.event import EventKind
from pipeline.stages.fusion import FusionHandler
from server.config import Settings
from tests.conftest import Harness


def test_three_repairs_two_nos_missing_audio_is_0_4() -> None:
    settings = Settings()
    score = fuse(None, None, 3, 2, False, settings)
    assert score == pytest.approx(0.4, abs=1e-6)


def test_uncalm_text_repairs_nos_barge_without_audio_is_0_6() -> None:
    settings = Settings()
    score = fuse(None, 0.0, 3, 2, True, settings)
    assert score == pytest.approx(0.6, abs=1e-6)


def test_starting_weights_cannot_reach_threshold_without_audio() -> None:
    settings = Settings()
    score = fuse(None, 0.0, 3, 2, True, settings)
    assert score < settings.frustration_threshold


def test_timeout_identical_to_none() -> None:
    settings = Settings()
    assert fuse(None, 0.5, 1, 0, False, settings) == pytest.approx(
        fuse(None, 0.5, 1, 0, False, settings),
        abs=1e-6,
    )


def test_calm_audio_zero_repairs_is_zero() -> None:
    settings = Settings()
    audio = EmotionProbs(calm=1.0, frustrated=0.0, distressed=0.0, generation=0)
    score = fuse(audio, 1.0, 0, 0, False, settings)
    assert score == pytest.approx(0.0, abs=1e-6)


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="fuse weights"):
        Settings(
            fuse_w_audio=0.5,
            fuse_w_text=0.5,
            fuse_w_repair=0.5,
            fuse_w_no=0.0,
            fuse_w_barge=0.0,
        )


async def test_session_repairs_and_barge_match_formula(harness: Harness) -> None:
    harness.session.repair_count = 3
    harness.session.repeated_no = 2
    harness.session.barge_in()
    captured: list[float] = []

    async def forward(event: object) -> None:
        captured.append(harness.session.fusion_score)

    handler = FusionHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        forward=forward,
    )
    event = harness.session.create_event(EventKind.NLU, {"spoken": "ok", "intent": "book"})
    await handler(event)
    expected = fuse(None, 0.5, 3, 2, True, harness.settings)
    assert captured[0] == pytest.approx(expected, abs=1e-6)
    assert captured[0] == pytest.approx(0.5, abs=1e-6)
