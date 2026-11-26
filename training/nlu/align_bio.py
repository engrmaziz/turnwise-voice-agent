"""Project clean BIO tags onto ASR tokens with Levenshtein alignment."""

from __future__ import annotations

from nlp.nlu_features import tokenize
from nlp.phonetic import jaro_winkler, metaphone

_KEEP_SCORE = 0.82


def bio_from_slots(text: str, slots: dict[str, str]) -> list[str]:
    """Tag slot values as BIO on whitespace tokens of ``text``."""
    tokens = tokenize(text)
    tags = ["O"] * len(tokens)
    ordered = sorted(slots.items(), key=lambda item: -len(item[1].split()))
    for key, value in ordered:
        needle = tokenize(value)
        if not needle:
            continue
        start = _find_subsequence(tokens, needle)
        if start is None:
            continue
        if any(tags[start + offset] != "O" for offset in range(len(needle))):
            continue
        tags[start] = f"B-{key}"
        for offset in range(1, len(needle)):
            tags[start + offset] = f"I-{key}"
    return tags


def project_bio(
    clean_tokens: list[str],
    clean_tags: list[str],
    asr_tokens: list[str],
) -> tuple[list[str], bool]:
    """Insertions are ``O``. Deletions drop the clean tag. Substitutions keep a tag
    only when the phonetic matcher treats the tokens as the same entity.
    """
    if len(clean_tokens) != len(clean_tags):
        raise ValueError("clean tokens and tags must align")
    ops = _align(clean_tokens, asr_tokens)
    tags: list[str] = []
    align_low = False
    last_slot = ""
    for op, clean_i, asr_i in ops:
        if op == "insert":
            tags.append("O")
            last_slot = ""
            continue
        if op == "delete":
            continue
        clean_tag = clean_tags[clean_i]
        if op == "equal":
            tags.append(_follow(clean_tag, last_slot))
            last_slot = _slot_of(tags[-1])
            continue
        if _same_entity(clean_tokens[clean_i], asr_tokens[asr_i]):
            tags.append(_follow(clean_tag, last_slot))
            last_slot = _slot_of(tags[-1])
        else:
            tags.append("O")
            last_slot = ""
            if clean_tag != "O":
                align_low = True
    return tags, align_low


def _follow(clean_tag: str, last_slot: str) -> str:
    slot = _slot_of(clean_tag)
    if not slot:
        return "O"
    if last_slot == slot and clean_tag.startswith("I-"):
        return clean_tag
    if last_slot == slot:
        return f"I-{slot}"
    return f"B-{slot}" if clean_tag.startswith(("B-", "I-")) else "O"


def _slot_of(tag: str) -> str:
    if tag.startswith("B-") or tag.startswith("I-"):
        return tag[2:]
    return ""


def _same_entity(clean: str, heard: str) -> bool:
    if clean.lower() == heard.lower():
        return True
    if metaphone(clean) == metaphone(heard) and metaphone(clean):
        return True
    return jaro_winkler(clean.lower(), heard.lower()) >= _KEEP_SCORE


def _find_subsequence(tokens: list[str], needle: list[str]) -> int | None:
    n = len(needle)
    for index in range(0, len(tokens) - n + 1):
        window = tokens[index : index + n]
        if [item.lower() for item in window] == [item.lower() for item in needle]:
            return index
    return None


def _align(clean: list[str], asr: list[str]) -> list[tuple[str, int, int]]:
    """Wagner-Fischer with equal / substitute / insert / delete ops on ASR order."""
    n_c = len(clean)
    n_a = len(asr)
    dist = [[0] * (n_a + 1) for _ in range(n_c + 1)]
    for i in range(1, n_c + 1):
        dist[i][0] = i
    for j in range(1, n_a + 1):
        dist[0][j] = j
    for i in range(1, n_c + 1):
        for j in range(1, n_a + 1):
            cost = 0 if clean[i - 1].lower() == asr[j - 1].lower() else 1
            dist[i][j] = min(
                dist[i - 1][j] + 1,
                dist[i][j - 1] + 1,
                dist[i - 1][j - 1] + cost,
            )
    ops: list[tuple[str, int, int]] = []
    i = n_c
    j = n_a
    while i > 0 or j > 0:
        same = i > 0 and j > 0 and clean[i - 1].lower() == asr[j - 1].lower()
        if same and dist[i][j] == dist[i - 1][j - 1]:
            ops.append(("equal", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dist[i][j] == dist[i - 1][j - 1] + 1:
            ops.append(("sub", i - 1, j - 1))
            i -= 1
            j -= 1
        elif j > 0 and dist[i][j] == dist[i][j - 1] + 1:
            ops.append(("insert", i, j - 1))
            j -= 1
        else:
            ops.append(("delete", i - 1, j))
            i -= 1
    ops.reverse()
    return ops
