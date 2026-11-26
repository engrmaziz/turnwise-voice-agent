"""Session-scoped FSM wrapper. Records visited states for tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dialogue.context import StepContext
from dialogue.slots import DialogueState
from dialogue.table import RejectFn, Table, TransitionFn, apply_event, classify_event, load_table
from server.config import Settings


class DialogueMachine:
    """One call. ``apply`` is the only way dialogue state moves."""

    def __init__(
        self,
        *,
        settings: Settings,
        roster: tuple[str, ...],
        timezone: ZoneInfo,
        now: datetime,
        table: Table | None = None,
        on_reject: RejectFn | None = None,
        on_transition: TransitionFn | None = None,
    ) -> None:
        self.settings = settings
        self.roster = roster
        self.timezone = timezone
        self.now = now
        self.table = table if table is not None else load_table()
        self.state = DialogueState()
        self.history: list[str] = [self.state.state_id]
        self._on_reject = on_reject
        self._on_transition = on_transition

    def start(self) -> DialogueState:
        return self.step(StepContext(event="session_start", settings=self.settings))

    def step(self, ctx: StepContext) -> DialogueState:
        filled = ctx
        if ctx.settings is None or ctx.roster == ():
            filled = StepContext(
                event=ctx.event,
                spoken=ctx.spoken,
                intent=ctx.intent,
                nlu_slots=ctx.nlu_slots,
                nlu_conf=ctx.nlu_conf,
                settings=self.settings,
                roster=self.roster or ctx.roster,
                now=ctx.now if ctx.now is not None else self.now,
                timezone=self.timezone,
                faq_chunk_id=ctx.faq_chunk_id,
                faq_reply=ctx.faq_reply,
                appointment_id=ctx.appointment_id,
                conflict_alts=ctx.conflict_alts,
                offer_latched=ctx.offer_latched,
                source=ctx.source,
            )
        elif ctx.now is None:
            filled = StepContext(
                event=ctx.event,
                spoken=ctx.spoken,
                intent=ctx.intent,
                nlu_slots=ctx.nlu_slots,
                nlu_conf=ctx.nlu_conf,
                settings=ctx.settings,
                roster=ctx.roster or self.roster,
                now=self.now,
                timezone=ctx.timezone,
                faq_chunk_id=ctx.faq_chunk_id,
                faq_reply=ctx.faq_reply,
                appointment_id=ctx.appointment_id,
                conflict_alts=ctx.conflict_alts,
                offer_latched=ctx.offer_latched,
                source=ctx.source,
            )
        previous = self.state
        nxt = apply_event(
            self.table,
            previous,
            filled,
            on_reject=self._on_reject,
            on_transition=self._on_transition,
        )
        self.state = nxt
        if nxt is not previous and (
            nxt.state_id != previous.state_id or nxt.state_id not in self.history
        ):
            self.history.append(nxt.state_id)
        return nxt

    def nlu(
        self,
        *,
        spoken: str,
        intent: str,
        slots: dict[str, str],
        conf: dict[str, float] | None = None,
        source: str = "nlu",
        offer_latched: bool = False,
    ) -> DialogueState:
        event = classify_event(self.state, spoken=spoken, intent=intent, settings=self.settings)
        return self.step(
            StepContext(
                event=event,
                spoken=spoken,
                intent=intent,
                nlu_slots=slots,
                nlu_conf=conf or {},
                settings=self.settings,
                roster=self.roster,
                now=self.now,
                timezone=self.timezone,
                offer_latched=offer_latched,
                source=source,
            )
        )
