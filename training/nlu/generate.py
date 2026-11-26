"""Hand-authored caller scripts. The LLM bench is blocked; this file is labeled hand_authored."""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from nlp.hotwords import load_roster
from nlp.nlu_vocab import INTENTS
from training.nlu.schema import (
    DISFLUENCY_MARKERS,
    FAKE_PATIENTS,
    PERSONAS,
    CallerScript,
)

SEED = 11
SOURCE_LABEL = "hand_authored"

_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_TIMES = ("nine", "ten thirty", "two", "two thirty", "four")
_PHONES = ("5550101234", "5550198765", "5550144444")
_IDS = ("A1001", "A2044", "A3310")
_FAQ = (
    "what are your hours",
    "do you take walk ins",
    "where is the clinic",
    "do I need a referral",
)
_URGENT = (
    "I have chest pain",
    "I cannot breathe well",
    "my chest hurts and I feel faint",
)
_OOS = (
    "can you refill my prescription",
    "I want to pay my electric bill",
    "book me a flight to Boston",
)


def generate_scripts(
    *, count: int, roster: tuple[str, ...], seed: int = SEED
) -> list[CallerScript]:
    rng = random.Random(seed)
    doctors = roster if roster else ("Dr. Avery Lang",)
    scripts: list[CallerScript] = []
    intent_cycle = (
        ["book"] * 40
        + ["reschedule"] * 30
        + ["cancel"] * 25
        + ["check_appointment"] * 25
        + ["faq"] * 25
        + ["speak_to_human"] * 20
        + ["urgent_symptom"] * 20
        + ["out_of_scope"] * 15
    )
    rng.shuffle(intent_cycle)
    while len(intent_cycle) < count:
        intent_cycle.append(rng.choice(intent_cycle))
    for index, intent in enumerate(intent_cycle[:count], start=1):
        persona = PERSONAS[index % 3]
        disfluent = persona == "disfluent"
        patient = rng.choice(FAKE_PATIENTS)
        doctor = rng.choice(doctors)
        day = rng.choice(_DAYS)
        time = rng.choice(_TIMES)
        phone = rng.choice(_PHONES)
        appt = rng.choice(_IDS)
        slots, text = _line(
            intent,
            persona=persona,
            disfluent=disfluent,
            patient=patient,
            doctor=doctor,
            day=day,
            time=time,
            phone=phone,
            appt=appt,
            rng=rng,
        )
        script = CallerScript(
            script_id=f"s{index:04d}",
            intent=intent,
            slots=slots,
            persona=persona,
            disfluency=disfluent,
            text=text,
        )
        script.validate_persona_disfluency()
        scripts.append(script)
    return scripts


def _line(
    intent: str,
    *,
    persona: str,
    disfluent: bool,
    patient: str,
    doctor: str,
    day: str,
    time: str,
    phone: str,
    appt: str,
    rng: random.Random,
) -> tuple[dict[str, str], str]:
    marker = rng.choice(DISFLUENCY_MARKERS)
    if intent == "book":
        slots = {
            "patient_name": patient,
            "phone": phone,
            "doctor": doctor,
            "date": day,
            "time": time,
        }
        if disfluent:
            other = "Thursday" if day != "Thursday" else "Friday"
            text = f"I need {doctor} on {other} {marker} {day} at {time} for {patient}"
        elif persona == "verbose":
            text = (
                f"hi this is {patient} my phone is {phone} I would like to book with "
                f"{doctor} on {day} at {time}"
            )
        else:
            text = f"book {doctor} {day} {time} for {patient} {phone}"
        return slots, text
    if intent == "reschedule":
        slots = {"appointment_id": appt, "date": day, "time": time}
        text = (
            f"move {appt} to {day} at {time}"
            if not disfluent
            else f"move {appt} to Monday {marker} {day} at {time}"
        )
        return slots, text
    if intent == "cancel":
        slots = {"appointment_id": appt}
        text = f"please cancel {appt}" if not disfluent else f"keep {appt} {marker} cancel {appt}"
        return slots, text
    if intent == "check_appointment":
        slots = {"patient_name": patient, "phone": phone}
        text = f"when is my visit I am {patient} {phone}"
        if disfluent:
            text = f"when is my visit I am {patient} {marker} yes {patient} {phone}"
        return slots, text
    if intent == "faq":
        query = rng.choice(_FAQ)
        slots = {"faq_query": query}
        text = query if not disfluent else f"{query} {marker} just the hours"
        return slots, text
    if intent == "speak_to_human":
        slots = {"reason": "billing"}
        text = (
            "I need to speak to a person about billing"
            if not disfluent
            else f"I can wait {marker} I need a person about billing"
        )
        return slots, text
    if intent == "urgent_symptom":
        text = rng.choice(_URGENT)
        if disfluent:
            text = f"it is nothing {marker} {text}"
        return {}, text
    text = rng.choice(_OOS)
    if disfluent:
        text = f"book a doctor {marker} {text}"
    return {}, text


def pick_fixture(scripts: list[CallerScript], count: int) -> list[CallerScript]:
    """Round-robin by intent so the 20-line CI file covers the closed set."""
    by_intent: dict[str, list[CallerScript]] = defaultdict(list)
    for script in scripts:
        by_intent[script.intent].append(script)
    picked: list[CallerScript] = []
    seen: set[str] = set()
    while len(picked) < count:
        progressed = False
        for intent in INTENTS:
            bucket = by_intent.get(intent, [])
            if not bucket:
                continue
            item = bucket.pop(0)
            if item.script_id in seen:
                continue
            picked.append(item)
            seen.add(item.script_id)
            progressed = True
            if len(picked) >= count:
                break
        if not progressed:
            break
    return picked


def write_jsonl(scripts: list[CallerScript], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"# source={SOURCE_LABEL} seed={SEED}\n")
        for script in scripts:
            handle.write(script.model_dump_json() + "\n")


def load_jsonl(path: Path) -> list[CallerScript]:
    rows: list[CallerScript] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        rows.append(CallerScript.model_validate_json(raw))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("training/nlu/scripts.jsonl"))
    parser.add_argument("--fixture", type=Path, default=Path("training/nlu/fixture_scripts.jsonl"))
    parser.add_argument("--roster", type=Path, default=Path("data/doctors.txt"))
    parser.add_argument("--fixture-count", type=int, default=20)
    args = parser.parse_args(argv)
    roster = load_roster(args.roster)
    scripts = generate_scripts(count=args.count, roster=roster)
    write_jsonl(scripts, args.out)
    write_jsonl(pick_fixture(scripts, args.fixture_count), args.fixture)
    print(
        f"source={SOURCE_LABEL} seed={SEED} wrote {len(scripts)} to {args.out} "
        f"and {args.fixture_count} to {args.fixture}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
