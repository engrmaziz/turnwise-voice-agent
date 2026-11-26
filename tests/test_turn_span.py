"""Parent turn span records first_audio_out. Payload stays off attributes."""

from opentelemetry.sdk.trace import ReadableSpan

from pipeline.trace_turn import CHILD_NAMES, TurnSpan
from tests.conftest import Harness


def _attrs(span: ReadableSpan) -> dict[str, object]:
    return dict(span.attributes or {})


def test_turn_span_parent_and_first_audio_out(harness: Harness) -> None:
    turn = TurnSpan()
    turn.open(
        harness.tracer,
        session_id=harness.session.session_id,
        turn_id=harness.session.turn_id,
        generation=harness.session.generation,
    )
    turn.mark(harness.tracer, "first_audio_out")
    turn.close(harness.tracer, reason="first_audio_out")
    finished = list(harness.exporter.get_finished_spans())
    names = {span.name for span in finished}
    assert "turn" in names
    assert "first_audio_out" in names
    assert "turn_end" in names
    parent = next(span for span in finished if span.name == "turn")
    attrs = _attrs(parent)
    assert "payload" not in attrs
    assert "patient_name" not in attrs
    skipped = [event for event in parent.events if event.name == "stage.skipped"]
    skipped_stages = {event.attributes["stage"] for event in skipped if event.attributes}
    assert "llm_ttft" in skipped_stages
    assert skipped_stages <= set(CHILD_NAMES)
