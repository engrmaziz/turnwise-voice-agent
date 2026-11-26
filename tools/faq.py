"""Local markdown FAQ. Score is token overlap until an ADR adds embeddings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class FaqChunk:
    chunk_id: str
    heading: str
    text: str


@dataclass(frozen=True, slots=True)
class FaqHit:
    chunk_id: str
    score: float
    reply: str


def load_chunks(path: Path) -> list[FaqChunk]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    chunks: list[FaqChunk] = []
    current_id = ""
    current_heading = ""
    body: list[str] = []
    index = 0
    for line in text.splitlines():
        if line.startswith("# "):
            if current_id:
                chunks.append(
                    FaqChunk(
                        chunk_id=current_id,
                        heading=current_heading,
                        text=" ".join(body).strip(),
                    )
                )
            index += 1
            current_heading = line[2:].strip()
            current_id = f"faq-{index:02d}"
            body = []
            continue
        if current_id:
            body.append(line.strip())
    if current_id:
        chunks.append(
            FaqChunk(chunk_id=current_id, heading=current_heading, text=" ".join(body).strip())
        )
    return chunks


def token_overlap(query: str, document: str) -> float:
    q = set(_TOKEN.findall(query.casefold()))
    d = set(_TOKEN.findall(document.casefold()))
    if not q:
        return 0.0
    return len(q & d) / len(q)


def retrieve(query: str, chunks: list[FaqChunk], *, min_score: float) -> FaqHit | None:
    best: FaqHit | None = None
    for chunk in chunks:
        blob = f"{chunk.heading} {chunk.text}"
        score = token_overlap(query, blob)
        if score < min_score:
            continue
        if best is None or score > best.score:
            best = FaqHit(
                chunk_id=chunk.chunk_id,
                score=score,
                reply=f"{chunk.text} [{chunk.chunk_id}]",
            )
    return best
