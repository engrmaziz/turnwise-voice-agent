"""Lexicon is deterministic. The optional local model flag does not change it."""

from nlp.sentiment import sentiment_score
from server.config import Settings


def test_please_and_thank_you_raise_calm() -> None:
    assert sentiment_score("please book that, thank you") > 0.5


def test_stupid_and_useless_lower_calm() -> None:
    assert sentiment_score("this is stupid and useless") < 0.5


def test_neutral_is_half() -> None:
    assert sentiment_score("book Tuesday at two") == 0.5


def test_sentiment_model_flag_defaults_false() -> None:
    settings = Settings()
    assert settings.sentiment_enabled is True
    assert settings.sentiment_model_enabled is False
    assert settings.emotion_model_enabled is False
