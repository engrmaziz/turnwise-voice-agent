"""Caller-script schema. Slot keys are appendix D. Names are invented."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from nlp.nlu_vocab import INTENTS, SLOT_KEYS

# SLURP is a format example only. It is not mixed into the JSONL and is not a
# source of clinic intents.

INTENT_SLOTS: dict[str, frozenset[str]] = {
    "book": frozenset({"patient_name", "phone", "doctor", "date", "time", "dob", "reason"}),
    "reschedule": frozenset(
        {"appointment_id", "patient_name", "phone", "date", "time", "doctor"}
    ),
    "cancel": frozenset({"appointment_id", "patient_name", "phone", "date"}),
    "check_appointment": frozenset({"patient_name", "phone", "appointment_id", "date"}),
    "faq": frozenset({"faq_query"}),
    "speak_to_human": frozenset({"reason"}),
    "urgent_symptom": frozenset(),
    "out_of_scope": frozenset(),
}

Persona = Literal["brief", "verbose", "disfluent"]
PERSONAS: tuple[Persona, ...] = ("brief", "verbose", "disfluent")
DISFLUENCY_MARKERS = ("no", "sorry", "I mean", "actually")

# Invented patients. Not a real directory.
FAKE_PATIENTS = (
    "Jordan Pike",
    "Riley Cho",
    "Sam Ortega",
    "Casey Belmont",
    "Avery Dunn",
    "Morgan Ellison",
    "Quinn Harlow",
    "Reese Calder",
    "Taylor Voss",
    "Jamie Pratt",
)


class CallerScript(BaseModel):
    """One synthetic caller line. ``text`` is free; intent and slot keys are closed."""

    script_id: str
    intent: str
    slots: dict[str, str] = Field(default_factory=dict)
    persona: Persona
    disfluency: bool
    text: str

    @field_validator("intent")
    @classmethod
    def known_intent(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in INTENTS:
            raise ValueError(f"unknown intent: {stripped}")
        return stripped

    @field_validator("slots")
    @classmethod
    def known_slots(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = [key for key in value if key not in SLOT_KEYS]
        if unknown:
            raise ValueError(f"slot not in appendix D: {unknown[0]}")
        return value

    @field_validator("text")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must be non-empty")
        return stripped

    def validate_persona_disfluency(self) -> None:
        if self.disfluency:
            lowered = self.text
            if not any(marker in lowered for marker in DISFLUENCY_MARKERS):
                raise ValueError("disfluent scripts must contain a repair marker")
        allowed = INTENT_SLOTS[self.intent]
        extra = [key for key in self.slots if key not in allowed]
        if extra:
            raise ValueError(f"slot {extra[0]} is not valid for intent {self.intent}")


class AsrTrainRow(BaseModel):
    script_id: str
    spoken_clean: str
    asr_text: str
    intent: str
    bio_asr: list[str]
    align_low: bool = False


class GoldenRow(AsrTrainRow):
    reviewer: str
    reviewed_at: str
    changed: bool = False
    waveform_id: str = ""

    @field_validator("asr_text")
    @classmethod
    def asr_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("asr_text is required")
        return value

    @model_validator(mode="after")
    def bio_matches_asr_tokens(self) -> GoldenRow:
        from nlp.nlu_features import tokenize

        if len(self.bio_asr) != len(tokenize(self.asr_text)):
            raise ValueError("bio_asr must align to asr_text tokens")
        return self
