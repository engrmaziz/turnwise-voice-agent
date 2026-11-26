"""Closed intent and slot vocabularies. Appendix D is the source of slot keys."""

INTENTS = (
    "book",
    "reschedule",
    "cancel",
    "check_appointment",
    "faq",
    "speak_to_human",
    "urgent_symptom",
    "out_of_scope",
)

SLOT_KEYS = (
    "patient_name",
    "phone",
    "doctor",
    "date",
    "time",
    "dob",
    "reason",
    "appointment_id",
    "faq_query",
)

BIO_TAGS = ("O", *tuple(f"{prefix}-{key}" for key in SLOT_KEYS for prefix in ("B", "I")))
INTENT_INDEX = {name: index for index, name in enumerate(INTENTS)}
TAG_INDEX = {name: index for index, name in enumerate(BIO_TAGS)}
