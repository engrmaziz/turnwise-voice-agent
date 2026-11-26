"""Deterministic TTS normalization. No LLM."""

from nlp.tn import TnContext, normalize_counted, normalize_for_tts
from pipeline.event import EventKind
from pipeline.stages.tts_norm import TtsNormHandler
from tests.conftest import Harness
from tests.support import counter_value


def test_time_phone_title_table() -> None:
    ctx = TnContext()
    time_spoken = normalize_for_tts("14:30", ctx)
    assert "two" in time_spoken
    assert "thirty" in time_spoken
    assert "p.m." in time_spoken or "pm" in time_spoken.replace(".", "")
    phone = normalize_for_tts("5550100", ctx)
    assert phone.split() == [
        "five",
        "five",
        "five",
        "zero",
        "one",
        "zero",
        "zero",
    ]
    titled = normalize_for_tts("Dr. Khan", ctx)
    assert titled.startswith("Doctor")


def test_unknown_name_character_becomes_symbol(harness: Harness) -> None:
    spoken, unknown = normalize_counted("K@n", TnContext(spell_name=True))
    assert "symbol" in spoken
    assert unknown == 1
    harness.metrics.tn_unknown_char.inc(unknown)
    assert counter_value(harness.metrics.tn_unknown_char) == 1.0


def test_confirm_inserts_a_comma() -> None:
    raw = "I will book Doctor Khan on November twenty-sixth at two thirty p.m. Is that right?"
    spoken = normalize_for_tts(raw, TnContext(confirm=True))
    assert "," in spoken
    assert spoken != raw or "," in raw


async def test_digit_mode_sets_tts_digit_speed(harness: Harness) -> None:
    captured: list[float] = []

    async def forward(event: object) -> None:
        payload = getattr(event, "payload", {})
        captured.append(float(payload.get("speed") or 0.0))

    handler = TtsNormHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        forward=forward,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {"text": "5 5 5", "digit_mode": 1, "filler": 0, "first_chunk": 1},
    )
    await handler(event)
    assert captured == [harness.settings.tts_digit_speed]


def test_tts_norm_module_does_not_import_llm() -> None:
    import inspect

    import pipeline.stages.tts_norm as mod

    source = inspect.getsource(mod)
    assert "llm_client" not in source
    assert "LlmClient" not in source
