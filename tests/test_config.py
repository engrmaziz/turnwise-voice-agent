"""Settings validation and env overrides."""

import pytest
from pydantic import SecretStr, ValidationError

from server.config import Settings, get_settings


def test_rejects_non_positive_queue_and_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(stage_queue_maxsize=0)
    with pytest.raises(ValidationError):
        Settings(stage_put_timeout_s=0)
    with pytest.raises(ValidationError):
        Settings(http_port=0)
    with pytest.raises(ValidationError):
        Settings(log_level="loud")


def test_blank_pii_key_from_the_environment_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TURNWISE_PII_HASH_KEY", "")
    settings = Settings()
    assert settings.pii_hash_key is None


def test_pii_key_round_trip() -> None:
    named = Settings(pii_hash_key=SecretStr("salt"))
    assert named.pii_hash_key is not None
    assert named.pii_hash_key.get_secret_value() == "salt"


def test_pii_field_names_split() -> None:
    settings = Settings(pii_fields="phone, dob ,")
    assert settings.pii_field_names == frozenset({"phone", "dob"})


def test_default_backchannel_list_excludes_yes() -> None:
    settings = Settings()
    assert "yes" not in settings.backchannel_list
    assert settings.backchannel_list == ("mm-hmm", "mhm", "uh-huh", "yeah", "ok", "okay")
    assert settings.endpoint_digit_patience_ms == 1000
    assert settings.turn_model_enabled is True
    assert settings.nlu_model_path == ""
    assert settings.nlu_timeout_ms == 40
    assert settings.phonetic_min_score == 0.82
    assert settings.phonetic_margin == 0.05
    assert settings.regex_slots_enabled is False
    assert settings.repair_handoff_after == 3
    assert settings.tool_filler_after_ms == 300
    assert settings.tts_backend == ""
    assert settings.tts_voice == "default"
    assert settings.tts_digit_speed == 0.85
    assert settings.tts_frame_ms == 20
    assert settings.tts_first_chunk_min_words == 4
    assert settings.tts_timeout_ms == 800
    assert settings.emotion_model_enabled is False
    assert settings.emotion_timeout_ms == 80
    assert settings.sentiment_enabled is True
    assert settings.sentiment_model_enabled is False
    assert settings.frustration_threshold == 0.65
    assert settings.frustration_turns == 2
    assert settings.tts_frustrated_speed == 0.9
    assert (
        settings.fuse_w_audio
        + settings.fuse_w_text
        + settings.fuse_w_repair
        + settings.fuse_w_no
        + settings.fuse_w_barge
        == 1.0
    )
    assert settings.eval_text_inject is False
    assert settings.eval_soft_judge is False
    assert settings.eval_time_scale == 0.0
    assert settings.eval_matrix_n == 900
    assert settings.eval_smoke_n == 30


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TURNWISE_STAGE_QUEUE_MAXSIZE", "4")
    monkeypatch.setenv("TURNWISE_LOG_LEVEL", "debug")
    settings = Settings()
    assert settings.stage_queue_maxsize == 4
    assert settings.log_level == "DEBUG"
    get_settings.cache_clear()
