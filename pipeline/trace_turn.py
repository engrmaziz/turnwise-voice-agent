"""Parent span per turn. Missing children are skip events, not invented spans."""

from __future__ import annotations

from opentelemetry.trace import Span, Tracer, set_span_in_context

CHILD_NAMES = (
    "vad",
    "asr_final",
    "turn_end",
    "nlu",
    "dm",
    "llm_ttft",
    "tts_first_chunk",
    "first_audio_out",
)


class TurnSpan:
    """Opened at TURN_END, closed on first content play-ack or session end."""

    __slots__ = ("_ended", "_generation", "_seen", "_session_id", "_span", "_turn_id")

    def __init__(self) -> None:
        self._span: Span | None = None
        self._seen: set[str] = set()
        self._ended = True
        self._session_id = ""
        self._turn_id = 0
        self._generation = 0

    def open(
        self,
        tracer: Tracer,
        *,
        session_id: str,
        turn_id: int,
        generation: int,
    ) -> None:
        self.close(tracer, reason="superseded")
        span = tracer.start_span("turn")
        span.set_attribute("session_id", session_id)
        span.set_attribute("turn_id", turn_id)
        span.set_attribute("generation", generation)
        self._span = span
        self._seen = set()
        self._ended = False
        self._session_id = session_id
        self._turn_id = turn_id
        self._generation = generation
        self.mark(tracer, "turn_end")

    def mark(self, tracer: Tracer, name: str) -> None:
        if self._span is None or self._ended or name not in CHILD_NAMES or name in self._seen:
            return
        self._seen.add(name)
        context = set_span_in_context(self._span)
        with tracer.start_as_current_span(name, context=context) as child:
            child.set_attribute("session_id", self._session_id)
            child.set_attribute("turn_id", self._turn_id)
            child.set_attribute("generation", self._generation)

    def close(self, tracer: Tracer | None = None, *, reason: str = "session_end") -> None:
        del tracer
        if self._span is None or self._ended:
            return
        for name in CHILD_NAMES:
            if name not in self._seen:
                self._span.add_event("stage.skipped", {"stage": name, "reason": reason})
        self._span.end()
        self._ended = True
        self._span = None
