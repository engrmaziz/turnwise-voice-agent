"""Exported spans on a book path do not carry plaintext names or phones."""

from pathlib import Path

from pipeline.event import Event, EventKind
from tests.conftest import Harness


def test_stage_sources_do_not_set_pii_attributes() -> None:
    needles = ("patient_name", "date_of_birth", "phone")
    hits: list[str] = []
    for root in (Path("pipeline"), Path("server")):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for index, line in enumerate(text.splitlines(), start=1):
                if "set_attribute" not in line:
                    continue
                if any(f'"{name}"' in line or f"'{name}'" in line for name in needles):
                    hits.append(f"{path}:{index}:{line.strip()}")
    assert hits == []


async def test_stage_span_omits_payload_name_and_phone(harness: Harness) -> None:
    seen: list[Event] = []

    async def handler(event: Event) -> None:
        seen.append(event)

    stage = harness.stage("nlu", handler)
    stage.start()
    event = harness.session.create_event(
        EventKind.NLU,
        {"spoken": "Ada Lovelace 5550100123", "patient_name": "Ada Lovelace"},
    )
    await stage.emit(event)
    await stage.inbox.join()
    await stage.aclose()
    assert seen
    blobs: list[str] = []
    for span in harness.exporter.get_finished_spans():
        blobs.append(span.name)
        for key, value in (span.attributes or {}).items():
            blobs.append(f"{key}={value!r}")
    joined = " ".join(blobs)
    assert "Ada" not in joined
    assert "5550100" not in joined
    assert "payload" not in joined
