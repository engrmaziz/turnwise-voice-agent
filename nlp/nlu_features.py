"""Hashed n-grams for the joint intent + BIO student. ``from_scratch``, not a transformer."""

from __future__ import annotations

from models.turn_features import hashed_vector

FEATURE_DIM = 256
NGRAM = 3
MAX_LENGTH = 128


def tokenize(text: str) -> list[str]:
    return [part for part in text.replace(",", " ").replace(".", " ").split() if part]


def intent_features(text: str, *, dim: int = FEATURE_DIM, ngram: int = NGRAM) -> list[float]:
    return hashed_vector(text, "intent", dim=dim, ngram=ngram, max_length=MAX_LENGTH)


def token_features(
    tokens: list[str],
    index: int,
    *,
    dim: int = FEATURE_DIM,
    ngram: int = NGRAM,
) -> list[float]:
    prev_tok = tokens[index - 1] if index > 0 else "<s>"
    next_tok = tokens[index + 1] if index + 1 < len(tokens) else "</s>"
    window = f"{prev_tok} {tokens[index]} {next_tok}"
    return hashed_vector(window, "bio", dim=dim, ngram=ngram, max_length=MAX_LENGTH)
