"""Build truncation JSONL from fixture sentences.

Each complete sentence yields one positive and at least one incomplete prefix.
``Wednesday`` is complete on slot ``date`` and incomplete on ``none`` when it is
the cut prefix of a longer booking request.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict


class TruncationRow(TypedDict):
    text: str
    slot: str
    complete: int
    source: str


_WEEKDAYS = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)
_LICENSE = (
    "# License: CC0-1.0. Synthetic clinic receptionist lines and public-domain "
    "calendar phrases. Not patient data. Generated for Turnwise truncation training."
)
_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_TIMES = (
    "eight",
    "eight thirty",
    "nine",
    "nine fifteen",
    "ten",
    "ten forty five",
    "eleven",
    "one",
    "two",
    "two thirty",
    "three",
    "four",
)
_DOCTORS = (
    "Avery Lang",
    "Nia Okonkwo",
    "Samir Qadir",
    "Helen Voss",
    "Priya Chaudhry",
    "Jonah Hale",
    "Mei Sorenson",
    "Rafael Ortiz",
    "Quinn Adler",
    "Yasmin Farouk",
    "Theo Brandt",
    "Lila Nguyen",
    "Marcus Pell",
    "Ingrid Strom",
    "Kofi Mensah",
)
_TEMPLATES = (
    "I need to book with Dr. {doctor} on {day} at {time}",
    "Please reschedule my visit with Dr. {doctor} to {day} at {time}",
    "Cancel my appointment with Dr. {doctor} on {day} at {time}",
    "Is Dr. {doctor} free on {day} around {time}",
)
_PUBLIC = (
    "The sun rose over the river at dawn",
    "A clock on the wall struck noon twice",
    "Leaves fell along the empty clinic walk",
    "Rain tapped the window through the night",
    "The waiting room chairs sat in two rows",
)


def generate_fixture_lines(*, target: int = 2000) -> list[str]:
    """Unique synthetic clinic lines plus a few public-domain sentences."""
    lines: list[str] = []
    seen: set[str] = set()
    for template in _TEMPLATES:
        for doctor in _DOCTORS:
            for day in _DAYS:
                for time in _TIMES:
                    text = template.format(doctor=doctor, day=day, time=time)
                    if text in seen:
                        continue
                    seen.add(text)
                    lines.append(text)
                    if len(lines) >= target:
                        return lines
    for extra in _PUBLIC:
        if extra not in seen:
            lines.append(extra)
            if len(lines) >= target:
                return lines
    return lines


def write_fixtures(path: Path, *, target: int = 2000) -> None:
    body = "\n".join([_LICENSE, *generate_fixture_lines(target=target)]) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def load_fixtures(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def slot_for(sentence: str) -> str:
    lower = sentence.lower()
    if any(day in lower for day in _WEEKDAYS) and "at " in lower:
        return "none"
    if any(day in lower for day in _WEEKDAYS):
        return "date"
    if any(ch.isdigit() for ch in sentence):
        return "phone"
    return "none"


def truncation_rows(sentence: str) -> list[TruncationRow]:
    """One complete row plus at least one incomplete prefix."""
    words = sentence.split()
    if not words:
        return []
    slot = slot_for(sentence)
    rows: list[TruncationRow] = [{"text": sentence, "slot": slot, "complete": 1, "source": "full"}]
    first = words[0]
    if first.lower() in _WEEKDAYS and len(words) > 1:
        rows.append({"text": first, "slot": "date", "complete": 1, "source": "weekday"})
        rows.append({"text": first, "slot": "none", "complete": 0, "source": "cut"})
    elif len(words) >= 2:
        mid = max(1, len(words) // 2)
        rows.append(
            {
                "text": " ".join(words[:mid]),
                "slot": "none",
                "complete": 0,
                "source": "prefix",
            }
        )
    else:
        rows.append({"text": first, "slot": "none", "complete": 0, "source": "cut"})
    return rows


def iter_rows(sentences: list[str]) -> Iterator[TruncationRow]:
    for sentence in sentences:
        yield from truncation_rows(sentence)


def write_jsonl(sentences: list[str], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in iter_rows(sentences):
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("training/turn/fixtures.txt"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("training/turn/truncation.jsonl"),
    )
    parser.add_argument("--write-fixtures", action="store_true")
    parser.add_argument("--target", type=int, default=2000)
    args = parser.parse_args(argv)
    if args.write_fixtures or not args.fixtures.is_file():
        write_fixtures(args.fixtures, target=args.target)
    sentences = load_fixtures(args.fixtures)
    count = write_jsonl(sentences, args.out)
    print(f"wrote {count} rows from {len(sentences)} sentences to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
