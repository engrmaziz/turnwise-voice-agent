"""Hashed character n-grams for the turn-completeness linear model.

Python's built-in ``hash`` is process-randomized. Training and ONNX inference
must share this blake2 index.
"""

from __future__ import annotations

import hashlib

FEATURE_DIM = 256
NGRAM = 3
MAX_LENGTH = 64


def hashed_vector(
    text: str,
    slot: str,
    *,
    dim: int = FEATURE_DIM,
    ngram: int = NGRAM,
    max_length: int = MAX_LENGTH,
) -> list[float]:
    """Return a ``dim``-length bag of character n-grams, slot-prefixed."""
    clipped = text.strip().lower()[:max_length]
    token = f"[{slot}] {clipped}"
    vec = [0.0] * dim
    compact = f" {token} "
    grams = [compact]
    for n in range(1, ngram + 1):
        limit = max(1, len(compact) - n + 1)
        grams.extend(compact[i : i + n] for i in range(limit))
    for gram in grams:
        vec[_stable_index(gram, dim)] += 1.0
    return vec


def _stable_index(gram: str, dim: int) -> int:
    digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % dim
