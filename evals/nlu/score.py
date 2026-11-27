"""Score teacher and student on the golden ASR column.

Slot F1 is not teacher-agreement. This module refuses files without reviewer.
``bio_projection`` is schema-validated BIO on recognizer text, not a waveform listen.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from evals.bench.harness import time_callable
from models.nlu_pool import NluScorer
from nlp.disfluency import spans_from_bio
from training.nlu.golden_sample import PROJECTION_REVIEWER
from training.nlu.schema import GoldenRow

# Slot F1 quoted as a human-listen SLO must come from waveform-reviewed rows.
# Teacher-agreement is not slot F1. Projection F1 is labeled separately.


class UnreviewedGoldenError(ValueError):
    """Golden file missing reviewer on a row."""


def load_golden(path: Path) -> list[GoldenRow]:
    rows: list[GoldenRow] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not str(payload.get("reviewer", "")).strip():
            raise UnreviewedGoldenError("golden row missing reviewer")
        rows.append(GoldenRow.model_validate(payload))
    if not rows:
        raise UnreviewedGoldenError("golden file is empty")
    return rows


def slot_micro_f1(pred_tags: list[str], gold_tags: list[str]) -> float:
    dummy = ["x"] * len(pred_tags)
    pred = {(span.slot, span.start, span.end) for span in spans_from_bio(dummy, pred_tags)}
    gold_dummy = ["x"] * len(gold_tags)
    gold = {(span.slot, span.start, span.end) for span in spans_from_bio(gold_dummy, gold_tags)}
    if not pred and not gold:
        return 1.0
    tp = len(pred & gold)
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(gold) if gold else 0.0
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def intent_accuracy(pred: list[str], gold: list[str]) -> float:
    if len(pred) != len(gold) or not gold:
        raise ValueError("intent lists must align")
    return sum(p == g for p, g in zip(pred, gold, strict=True)) / len(gold)


def score_file(
    path: Path,
    *,
    intent_onnx: Path | None = None,
    bio_onnx: Path | None = None,
) -> dict[str, object]:
    rows = load_golden(path)
    gold_intents = [row.intent for row in rows]
    reviewers = sorted({row.reviewer for row in rows})
    waveform_listen = (
        len(rows) >= 500
        and bool(reviewers)
        and all(reviewer != PROJECTION_REVIEWER for reviewer in reviewers)
    )
    payload: dict[str, object] = {
        "n": len(rows),
        "reviewers": reviewers,
        "waveform_listen": waveform_listen,
        "identity_intent_accuracy": intent_accuracy(gold_intents, gold_intents),
        "identity_slot_f1": sum(slot_micro_f1(row.bio_asr, row.bio_asr) for row in rows)
        / len(rows),
        "note": _note(len(rows), waveform_listen, student=False),
    }
    if intent_onnx is None or bio_onnx is None:
        return payload
    if not intent_onnx.is_file() or not bio_onnx.is_file():
        payload["student"] = "missing_onnx"
        return payload
    scorer = NluScorer.load(intent_onnx, bio_onnx, timeout_ms=1000)
    infer = scorer.infer_sync
    if infer is None:
        scorer.close()
        payload["student"] = "missing_infer"
        return payload
    try:
        hyps = [infer(row.asr_text) for row in rows]
    finally:
        scorer.close()
    pred_intents = [hyp.intent for hyp in hyps]
    slot_scores = [
        slot_micro_f1(list(hyp.tags), row.bio_asr) for hyp, row in zip(hyps, rows, strict=True)
    ]
    payload["student_intent_accuracy"] = intent_accuracy(pred_intents, gold_intents)
    payload["student_slot_f1"] = sum(slot_scores) / len(slot_scores)
    payload["note"] = _note(len(rows), waveform_listen, student=True)
    return payload


def _note(n: int, waveform_listen: bool, *, student: bool) -> str:
    if not student:
        return "identity ceiling only; unpublished unless golden is 500 reviewed rows"
    if n < 500:
        return "student scores on fewer than 500 rows; not a published F1"
    if waveform_listen:
        return "student scores on 500 waveform-reviewed rows"
    return (
        "student scores on 500 Zipformer-ASR rows with BIO projection; "
        "not a waveform listen"
    )


def measure_student_latency_ms(
    predict: Callable[[str], object], text: str, *, warmup: int, samples: int
) -> tuple[float, float]:
    def once() -> None:
        predict(text)

    p50, p95, _ = time_callable(once, warmup=warmup, samples=samples)
    return p50, p95


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=Path("training/nlu/golden_fixture.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase5_score.json"))
    parser.add_argument("--intent-onnx", type=Path, default=None)
    parser.add_argument("--bio-onnx", type=Path, default=None)
    args = parser.parse_args(argv)
    payload = score_file(args.golden, intent_onnx=args.intent_onnx, bio_onnx=args.bio_onnx)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
