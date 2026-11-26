"""Template replies. Over-long paraphrase is discarded."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from models.llm_client import LlmClient, LlmGrammarError, LlmTimeoutError
from server.config import Settings


class ParaphraseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


TEMPLATES: dict[str, str] = {
    "greet": "Hello, this is Turnwise Clinic.",
    "ask_intent": "Are you calling to book, move, or cancel a visit?",
    "ask_slot": "I still need that detail.",
    "spell_or_digits": "Please spell that, or say the digits one at a time.",
    "confirm_readback": "I will book that now. Is that right?",
    "booked": "Your visit is booked.",
    "reoffer": "That time was just taken. I can offer another slot.",
    "handoff_summary": "I will put you through to the front desk.",
    "seek_emergency": "If this is an emergency, hang up and call emergency services now.",
    "faq_refuse": "I do not have that in the clinic FAQ.",
    "goodbye": "Goodbye.",
    "one_moment": "One moment.",
    "cannot_book_now": "I cannot book that right now.",
    "ask_intent_oos": "I can help with booking, moving, or cancelling a visit.",
}


async def speak(
    template_id: str,
    *,
    fallback: str,
    settings: Settings,
    llm: LlmClient | None,
    paraphrase: bool = False,
) -> str:
    template = TEMPLATES.get(template_id, fallback)
    if not paraphrase or llm is None or not llm.available:
        return template
    try:
        payload = await llm.complete_json(
            f"Paraphrase in under {settings.paraphrase_max_chars} characters: {template}",
            ParaphraseSchema,
        )
    except (LlmGrammarError, LlmTimeoutError):
        return template
    text = str(payload.get("text", "")).strip()
    if not text or len(text) > settings.paraphrase_max_chars:
        return template
    return text
