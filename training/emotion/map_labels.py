"""Map CREMA-D and RAVDESS labels onto calm / frustrated / distressed."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Happy and neutral → calm. Angry and disgust → frustrated. Fear and sad → distressed.
# Unmapped labels are dropped and counted, never exposed to the FSM.

CREMA_D: dict[str, str] = {
    "HAP": "calm",
    "NEU": "calm",
    "ANG": "frustrated",
    "DIS": "frustrated",
    "FEA": "distressed",
    "SAD": "distressed",
}

RAVDESS: dict[str, str] = {
    "01": "calm",  # neutral
    "02": "calm",  # calm
    "03": "calm",  # happy
    "04": "distressed",  # sad
    "05": "frustrated",  # angry
    "06": "distressed",  # fearful
    "07": "frustrated",  # disgust
    # 08 surprised is unmapped
}

CLASSES = ("calm", "frustrated", "distressed")


@dataclass(slots=True, frozen=True)
class MappedLabel:
    path: Path
    source: str
    raw: str
    mapped: str | None


def crema_raw_from_name(name: str) -> str:
    """CREMA-D files look like ``1001_DFA_ANG_XX.wav``; emotion is the third token."""
    stem = Path(name).stem
    parts = stem.split("_")
    if len(parts) < 3:
        return ""
    return parts[2].upper()


def ravdess_raw_from_name(name: str) -> str:
    """RAVDESS files look like ``03-01-06-01-02-01-12.wav``; emotion is field 3."""
    stem = Path(name).stem
    parts = stem.split("-")
    if len(parts) < 3:
        return ""
    return parts[2]


def map_crema(raw: str) -> str | None:
    return CREMA_D.get(raw.upper())


def map_ravdess(raw: str) -> str | None:
    return RAVDESS.get(raw)


def map_file(path: Path, source: str) -> MappedLabel:
    if source == "crema":
        raw = crema_raw_from_name(path.name)
        mapped = map_crema(raw)
    elif source == "ravdess":
        raw = ravdess_raw_from_name(path.name)
        mapped = map_ravdess(raw)
    else:
        raise ValueError(f"unknown source {source}")
    return MappedLabel(path=path, source=source, raw=raw, mapped=mapped)


def map_tree(root: Path, source: str) -> tuple[tuple[MappedLabel, ...], int]:
    """Return mapped rows and the unmapped count."""
    rows: list[MappedLabel] = []
    dropped = 0
    for path in sorted(root.rglob("*.wav")):
        row = map_file(path, source)
        rows.append(row)
        if row.mapped is None:
            dropped += 1
    return tuple(rows), dropped
