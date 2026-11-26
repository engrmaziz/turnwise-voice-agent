"""NLU stage reads spoken text, resolves doctor to a catalog id, times out cleanly."""

import json
from pathlib import Path

from models.nlu_pool import NluHypothesis, NluScorer
from nlp.hotwords import load_roster
from pipeline.event import Event, EventKind
from pipeline.stages.nlu import NluHandler
from tests.conftest import Harness


def _hypo_lan() -> NluHypothesis:
    return NluHypothesis(
        intent="book",
        intent_confidence=0.9,
        tokens=("book", "with", "Lan", "on", "Tuesday"),
        tags=("O", "O", "B-doctor", "O", "B-date"),
    )


async def test_doctor_slot_is_catalog_id(harness: Harness) -> None:
    emitted: list[Event] = []

    async def forward(event: Event) -> None:
        emitted.append(event)

    roster = load_roster(Path("data/doctors.txt"))
    handler = NluHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=NluScorer.stub(timeout_ms=40, hypothesis=_hypo_lan()),
        metrics=harness.metrics,
        forward=forward,
        roster=roster,
    )
    event = harness.session.create_event(
        EventKind.FINAL,
        {"spoken": "book with Lan on Tuesday"},
    )
    await handler(event)
    assert handler.emitted == 1
    nlu = emitted[0]
    assert nlu.kind is EventKind.NLU
    slots = json.loads(str(nlu.payload["slots"]))
    assert slots["doctor"] == "Dr. Avery Lang"
    assert slots["doctor"] != "Lan"


async def test_timeout_emits_nlu_ok_zero(harness: Harness) -> None:
    emitted: list[Event] = []

    async def forward(event: Event) -> None:
        emitted.append(event)

    handler = NluHandler(
        session=harness.session,
        settings=harness.settings.model_copy(update={"nlu_timeout_ms": 20}),
        scorer=NluScorer.stub(timeout_ms=20, hypothesis=_hypo_lan(), sleep_s=0.2),
        metrics=harness.metrics,
        forward=forward,
        roster=("Dr. Avery Lang",),
    )
    await handler(harness.session.create_event(EventKind.FINAL, {"spoken": "book with Lan"}))
    nlu = emitted[0]
    assert nlu.payload["nlu_ok"] == 0
    assert nlu.payload["intent"] == ""


async def test_substitution_keeps_student_spans(harness: Harness) -> None:
    emitted: list[Event] = []

    async def forward(event: Event) -> None:
        emitted.append(event)

    handler = NluHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=NluScorer.stub(timeout_ms=40, hypothesis=_hypo_lan()),
        metrics=harness.metrics,
        forward=forward,
        roster=load_roster(Path("data/doctors.txt")),
    )
    await handler(
        harness.session.create_event(EventKind.FINAL, {"spoken": "book with Lan on Tuesday"})
    )
    slots = json.loads(str(emitted[0].payload["slots"]))
    assert slots["date"] == "Tuesday"


async def test_unavailable_emits_nlu_ok_zero(harness: Harness) -> None:
    emitted: list[Event] = []

    async def forward(event: Event) -> None:
        emitted.append(event)

    handler = NluHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=NluScorer.unavailable(timeout_ms=40),
        metrics=harness.metrics,
        forward=forward,
        roster=("Dr. Avery Lang",),
    )
    await handler(harness.session.create_event(EventKind.FINAL, {"spoken": "book tuesday"}))
    assert emitted[0].payload["nlu_ok"] == 0


async def test_reads_spoken_not_normalized(harness: Harness) -> None:
    emitted: list[Event] = []

    async def forward(event: Event) -> None:
        emitted.append(event)

    handler = NluHandler(
        session=harness.session,
        settings=harness.settings,
        scorer=NluScorer.stub(timeout_ms=40, hypothesis=_hypo_lan()),
        metrics=harness.metrics,
        forward=forward,
        roster=load_roster(Path("data/doctors.txt")),
    )
    await handler(
        harness.session.create_event(
            EventKind.FINAL,
            {"spoken": "book with Lan on Tuesday", "normalized": "ignore me"},
        )
    )
    assert emitted[0].payload["spoken"] == "book with Lan on Tuesday"


def test_app_source_does_not_import_regex_slots() -> None:
    text = Path("server/app.py").read_text(encoding="utf-8")
    assert "regex_slots" not in text
