"""ITN keeps spoken form. Partials are never normalized."""

import time

from nlp.itn import apply_rules, inverse_normalize, inverse_normalize_sync, nemo_import_status


def test_two_thirty_contains_clock() -> None:
    written = apply_rules("march third at two thirty")
    assert "2:30" in written
    assert "March 3" in written


def test_exception_keeps_spoken() -> None:
    def boom(_text: str) -> str:
        raise RuntimeError("itn exploded")

    result = inverse_normalize_sync("two thirty", transform=boom)
    assert result.spoken == "two thirty"
    assert result.normalized == "two thirty"
    assert result.ok is False


def test_nemo_status_is_recorded() -> None:
    status = nemo_import_status()
    assert status == "imported" or status.endswith("Error") or status.endswith("Warning")


async def test_timeout_keeps_spoken() -> None:
    def slow(text: str) -> str:
        time.sleep(0.2)
        return text

    result = await inverse_normalize("two thirty", timeout_s=0.02, transform=slow)
    assert result.ok is False
    assert result.spoken == "two thirty"
    assert result.engine == "timeout"
