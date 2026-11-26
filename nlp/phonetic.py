"""Closed-set entity resolve. Titles are stripped; the function does not write a DB."""

from __future__ import annotations

from dataclasses import dataclass

from server.config import Settings

_TITLES = ("dr.", "dr", "doctor")


@dataclass(frozen=True, slots=True)
class ResolveResult:
    """One catalog id, or none plus a short candidate list."""

    entity_id: str | None
    candidates: tuple[str, ...]
    top_score: float
    runner_up: float


def strip_title(text: str) -> str:
    """Lowercase and drop a leading doctor title."""
    compact = " ".join(text.lower().split())
    for title in _TITLES:
        prefix = f"{title} "
        if compact.startswith(prefix):
            return compact[len(prefix) :].strip()
    if compact in _TITLES:
        return ""
    return compact


def jaro_winkler(left: str, right: str) -> float:
    """Jaro-Winkler similarity in ``[0, 1]``. Prefix scale is 0.1, max 4."""
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    jaro = _jaro(left, right)
    prefix = 0
    for a, b in zip(left, right, strict=False):
        if a != b or prefix == 4:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1.0 - jaro)


def metaphone(word: str) -> str:
    """English Metaphone code. Clinic names are Latin-script."""
    letters = "".join(ch for ch in word.upper() if "A" <= ch <= "Z")
    if not letters:
        return ""
    chars = list(letters)
    if chars[0:2] == ["K", "N"] or chars[0:2] == ["G", "N"] or chars[0:2] == ["P", "N"]:
        chars = chars[1:]
    if chars[0:2] == ["A", "E"]:
        chars = chars[1:]
    if chars[0] == "X":
        chars[0] = "S"
    if chars[0] == "W" and len(chars) > 1 and chars[1] == "H":
        chars = chars[1:]
    out: list[str] = []
    i = 0
    length = len(chars)
    while i < length:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < length else ""
        if ch in {"A", "E", "I", "O", "U", "Y"}:
            if i == 0:
                out.append(ch)
            i += 1
            continue
        if ch == "B":
            if not (i == length - 1 and out and out[-1] == "P"):
                out.append("B")
        elif ch == "C":
            if nxt == "H":
                out.append("X")
                i += 2
                continue
            if nxt in {"I", "E", "Y"}:
                out.append("S")
            else:
                out.append("K")
        elif ch == "D":
            if nxt == "G" and i + 2 < length and chars[i + 2] in {"I", "E", "Y"}:
                out.append("J")
                i += 3
                continue
            out.append("T")
        elif ch == "F":
            out.append("F")
        elif ch == "G":
            if nxt in {"I", "E", "Y"}:
                out.append("J")
            else:
                out.append("K")
        elif ch == "H":
            if i > 0 and chars[i - 1] not in {"A", "E", "I", "O", "U"}:
                i += 1
                continue
            out.append("H")
        elif ch == "J":
            out.append("J")
        elif ch == "K":
            if i == 0 or chars[i - 1] != "C":
                out.append("K")
        elif ch == "L":
            out.append("L")
        elif ch == "M":
            out.append("M")
        elif ch == "N":
            out.append("N")
        elif ch == "P":
            out.append("F" if nxt == "H" else "P")
            if nxt == "H":
                i += 2
                continue
        elif ch == "Q":
            out.append("K")
        elif ch == "R":
            out.append("R")
        elif ch == "S":
            out.append("X" if nxt == "H" else "S")
            if nxt == "H":
                i += 2
                continue
        elif ch == "T":
            if nxt == "H":
                out.append("0")
                i += 2
                continue
            out.append("T")
        elif ch == "V":
            out.append("F")
        elif ch == "W":
            if nxt in {"A", "E", "I", "O", "U"}:
                out.append("W")
        elif ch == "X":
            out.append("KS")
        elif ch == "Z":
            out.append("S")
        i += 1
    collapsed: list[str] = []
    for ch in "".join(out):
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    return "".join(collapsed)[:6]


def phonetic_score(heard: str, candidate: str) -> float:
    """``0.6 * JW(metaphone) + 0.4 * JW(surface)`` after title strip."""
    a = strip_title(heard)
    b = strip_title(candidate)
    if not a or not b:
        return 0.0
    surfaces = [b]
    parts = b.split()
    if parts:
        surfaces.append(parts[-1])
    best = 0.0
    for surface in surfaces:
        meta = 0.6 * jaro_winkler(metaphone(a), metaphone(surface))
        raw = 0.4 * jaro_winkler(a, surface)
        best = max(best, meta + raw)
    return best


def resolve_entity(heard: str, candidates: list[str], settings: Settings) -> ResolveResult:
    """Return one id, or none plus up to three candidates on a low score or tie."""
    if not heard.strip() or not candidates:
        return ResolveResult(entity_id=None, candidates=(), top_score=0.0, runner_up=0.0)
    ranked = sorted(
        ((phonetic_score(heard, item), item) for item in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )
    top_score, top_id = ranked[0]
    runner = ranked[1][0] if len(ranked) > 1 else 0.0
    names = tuple(item for _score, item in ranked[:3])
    if top_score < settings.phonetic_min_score:
        return ResolveResult(
            entity_id=None, candidates=names, top_score=top_score, runner_up=runner
        )
    if len(ranked) > 1 and (top_score - runner) < settings.phonetic_margin:
        return ResolveResult(
            entity_id=None, candidates=names, top_score=top_score, runner_up=runner
        )
    return ResolveResult(entity_id=top_id, candidates=names, top_score=top_score, runner_up=runner)


def _jaro(left: str, right: str) -> float:
    len_l = len(left)
    len_r = len(right)
    match_dist = max(len_l, len_r) // 2 - 1
    match_dist = max(0, match_dist)
    left_hit = [False] * len_l
    right_hit = [False] * len_r
    matches = 0
    for i, ch in enumerate(left):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len_r)
        for j in range(start, end):
            if right_hit[j] or right[j] != ch:
                continue
            left_hit[i] = True
            right_hit[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    k = 0
    trans = 0
    for i, hit in enumerate(left_hit):
        if not hit:
            continue
        while not right_hit[k]:
            k += 1
        if left[i] != right[k]:
            trans += 1
        k += 1
    trans_f = trans / 2.0
    return (matches / len_l + matches / len_r + (matches - trans_f) / matches) / 3.0
