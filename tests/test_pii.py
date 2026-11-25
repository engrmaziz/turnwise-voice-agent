"""PII redaction hashes configured fields and never keeps a payload."""

from pydantic import SecretStr

from server.config import Settings
from server.log_setup import configure_logging
from server.pii import PiiRedactor


def _settings(key: str | None) -> Settings:
    secret = None if key is None else SecretStr(key)
    return Settings(log_level="INFO", pii_hash_key=secret, otel_enabled=False)


def test_hash_is_stable_for_a_key_and_differs_across_keys() -> None:
    first = PiiRedactor(_settings("alpha"))
    second = PiiRedactor(_settings("alpha"))
    other = PiiRedactor(_settings("beta"))
    assert first.hash_value("Ada Lovelace") == second.hash_value("Ada Lovelace")
    assert first.hash_value("Ada Lovelace") != other.hash_value("Ada Lovelace")
    assert first.hash_value("Ada Lovelace") != first.hash_value("Ada")
    assert first.hash_value("Ada Lovelace").startswith("hmac-sha256:")


def test_processor_hashes_fields_and_omits_payload() -> None:
    redactor = PiiRedactor(_settings("alpha"))
    event: dict[str, object] = {
        "event": "booked",
        "patient_name": "Ada Lovelace",
        "phone": "5550100",
        "payload": {"patient_name": "Ada Lovelace", "note": "secret"},
        "turn_id": 3,
    }
    cleaned = redactor.processor(None, "info", event)
    assert cleaned["event"] == "booked"
    assert cleaned["turn_id"] == 3
    assert cleaned["payload"] == "omitted"
    assert cleaned["patient_name"] == redactor.hash_value("Ada Lovelace")
    assert cleaned["phone"] == redactor.hash_value("5550100")
    assert "Ada Lovelace" not in str(cleaned["patient_name"])
    assert "5550100" not in str(cleaned)


def test_non_scalar_pii_is_not_stringified_into_the_log() -> None:
    redactor = PiiRedactor(_settings("alpha"))
    event: dict[str, object] = {"patient_name": {"raw": "Ada Lovelace"}}
    cleaned = redactor.processor(None, "info", event)
    assert cleaned["patient_name"] == "redacted-non-scalar"
    assert "Ada Lovelace" not in str(cleaned)


def test_missing_key_is_ephemeral_and_configure_logging_accepts_it() -> None:
    settings = _settings(None)
    redactor = PiiRedactor(settings)
    assert redactor.ephemeral is True
    configure_logging(settings, redactor)
    redactor.warn_if_ephemeral()
