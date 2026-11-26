"""Template replies. Over-long or slot-dropping paraphrase is discarded."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from dialogue.slots import (
    DialogueState,
    SlotValue,
    confirmed_only,
    missing_required,
    next_ask_slot,
)
from dialogue.templates import Template, TemplateCatalog, load_templates
from models.llm_client import LlmClient, LlmGrammarError, LlmTimeoutError
from nlp.tn import TnContext, normalize_for_tts
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class ParaphraseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


def fill_template(text: str, slots: dict[str, str]) -> str:
    """Substitute confirmed values. Missing keys become empty strings."""

    def repl(match: re.Match[str]) -> str:
        return slots.get(match.group(1), "")

    filled = _PLACEHOLDER.sub(repl, text)
    return re.sub(r"\s+", " ", filled).strip()


def select_template_text(
    action: str,
    state: DialogueState,
    catalog: TemplateCatalog | None = None,
    *,
    short: bool = False,
) -> tuple[str, str]:
    loaded = catalog if catalog is not None else load_templates()
    tmpl = loaded.require_action(action)
    confirmed = confirmed_only(state.slots)
    if action == "say_faq" and state.played_text:
        confirmed = {**confirmed, "faq": state.played_text}
    slot = next_ask_slot(state.intent, state.slots)
    if slot:
        confirmed = {**confirmed, "slot": slot}
    chosen_id = tmpl.id
    chosen_text = tmpl.text
    if short and tmpl.short:
        chosen_text = tmpl.short
    elif tmpl.ask and missing_required(state.intent, state.slots):
        chosen_text = tmpl.ask
    override = (state.last_template or "").split(":")[0]
    if override and override != tmpl.id:
        chosen_id, chosen_text = _override_template(loaded, tmpl, override, state, short=short)
    return chosen_id, fill_template(chosen_text, confirmed)


def _override_template(
    loaded: TemplateCatalog,
    tmpl: Template,
    override: str,
    state: DialogueState,
    *,
    short: bool = False,
) -> tuple[str, str]:
    if override in loaded.by_action:
        other = loaded.by_action[override]
        text = other.text
        if short and other.short:
            text = other.short
        elif other.ask and missing_required(state.intent, state.slots):
            text = other.ask
        return other.id, text
    alt = loaded.by_id.get(override) or loaded.warmup.get(override)
    if alt is not None:
        return override, alt
    return tmpl.id, tmpl.text


def required_surface_forms(slots: dict[str, str], context: TnContext) -> set[str]:
    """TN forms that a paraphrase must still contain."""
    forms: set[str] = set()
    for key in ("doctor", "date", "time", "phone", "appointment_id"):
        value = slots.get(key, "").strip()
        if not value:
            continue
        spoken = normalize_for_tts(value, context)
        if spoken:
            forms.add(spoken.casefold())
    return forms


async def speak(
    template_id: str,
    *,
    fallback: str,
    settings: Settings,
    llm: LlmClient | None,
    paraphrase: bool = False,
    slots: dict[str, SlotValue] | None = None,
    metrics: StageMetrics | None = None,
    catalog: TemplateCatalog | None = None,
    session: Session | None = None,
) -> str:
    loaded = catalog if catalog is not None else load_templates()
    catalog_text = loaded.text_for_id(template_id, fallback)
    template = fallback if fallback else catalog_text
    if not paraphrase or llm is None or not llm.available:
        return template
    if session is not None and session.tracer is not None:
        session.turn_span.mark(session.tracer, "llm_ttft")
    try:
        payload = await llm.complete_json(
            f"Paraphrase in under {settings.paraphrase_max_chars} characters: {template}",
            ParaphraseSchema,
            speaking=True,
        )
    except (LlmGrammarError, LlmTimeoutError):
        return template
    text = str(payload.get("text", "")).strip()
    if not text or len(text) > settings.paraphrase_max_chars:
        if metrics is not None:
            metrics.planner_paraphrase_discard.labels(reason="length").inc()
        return template
    confirmed = confirmed_only(slots or {})
    context = TnContext(spell_name=False, digit_mode=False, confirm=False)
    needed = required_surface_forms(confirmed, context)
    spoken_para = normalize_for_tts(text, context).casefold()
    if any(form not in spoken_para for form in needed):
        if metrics is not None:
            metrics.planner_paraphrase_discard.labels(reason="missing_slot").inc()
        return template
    return text
