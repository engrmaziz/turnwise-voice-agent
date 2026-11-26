"""Train a from_scratch joint intent + BIO linear student.

STARTING POINT from plan T5.4.1 (encoder-scale): lr=3e-5, epochs=5, batch=16,
max length=128. This file trains hashed-ngram linear heads, so TRAIN_LR is 0.1.
Do not claim a transformer. Encoder name is from_scratch; ADR-004 is blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from nlp.nlu_features import FEATURE_DIM, NGRAM, intent_features, token_features, tokenize
from nlp.nlu_vocab import BIO_TAGS, INTENT_INDEX, INTENTS, TAG_INDEX
from training.nlu.schema import AsrTrainRow

PLAN_LR = 3e-5
PLAN_EPOCHS = 5
PLAN_BATCH = 16
TRAIN_LR = 0.1
TRAIN_EPOCHS = 5
TRAIN_BATCH = 16
SEED = 13


def _softmax(logits: list[float]) -> list[float]:
    peak = max(logits)
    exps = [math.exp(v - peak) for v in logits]
    total = sum(exps)
    return [v / total for v in exps]


def _one_hot(index: int, size: int) -> list[float]:
    row = [0.0] * size
    row[index] = 1.0
    return row


def load_rows(path: Path) -> list[AsrTrainRow]:
    rows: list[AsrTrainRow] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        rows.append(AsrTrainRow.model_validate_json(raw))
    return rows


def train_student(
    rows: list[AsrTrainRow],
    *,
    lr: float = TRAIN_LR,
    epochs: int = TRAIN_EPOCHS,
    batch: int = TRAIN_BATCH,
    seed: int = SEED,
) -> dict[str, object]:
    rng = random.Random(seed)
    intent_w = [[0.0] * FEATURE_DIM for _ in INTENTS]
    intent_b = [0.0] * len(INTENTS)
    bio_w = [[0.0] * FEATURE_DIM for _ in BIO_TAGS]
    bio_b = [0.0] * len(BIO_TAGS)
    examples = list(rows)
    for _ in range(epochs):
        rng.shuffle(examples)
        for start in range(0, len(examples), batch):
            chunk = examples[start : start + batch]
            g_iw = [[0.0] * FEATURE_DIM for _ in INTENTS]
            g_ib = [0.0] * len(INTENTS)
            g_bw = [[0.0] * FEATURE_DIM for _ in BIO_TAGS]
            g_bb = [0.0] * len(BIO_TAGS)
            for row in chunk:
                x = intent_features(row.asr_text)
                logits = [
                    intent_b[i] + sum(a * b for a, b in zip(intent_w[i], x, strict=True))
                    for i in range(len(INTENTS))
                ]
                probs = _softmax(logits)
                target = INTENT_INDEX[row.intent]
                err = [p - t for p, t in zip(probs, _one_hot(target, len(INTENTS)), strict=True)]
                for i, e in enumerate(err):
                    g_ib[i] += e
                    for j, val in enumerate(x):
                        g_iw[i][j] += e * val
                tokens = tokenize(row.asr_text)
                tags = row.bio_asr
                limit = min(len(tokens), len(tags))
                for index in range(limit):
                    tag = tags[index]
                    if tag not in TAG_INDEX:
                        continue
                    tx = token_features(tokens, index)
                    t_logits = [
                        bio_b[i] + sum(a * b for a, b in zip(bio_w[i], tx, strict=True))
                        for i in range(len(BIO_TAGS))
                    ]
                    t_probs = _softmax(t_logits)
                    t_err = [
                        p - t
                        for p, t in zip(
                            t_probs, _one_hot(TAG_INDEX[tag], len(BIO_TAGS)), strict=True
                        )
                    ]
                    for i, e in enumerate(t_err):
                        g_bb[i] += e
                        for j, val in enumerate(tx):
                            g_bw[i][j] += e * val
            scale = lr / max(1, len(chunk))
            for i in range(len(INTENTS)):
                intent_b[i] -= scale * g_ib[i]
                intent_w[i] = [w - scale * g for w, g in zip(intent_w[i], g_iw[i], strict=True)]
            for i in range(len(BIO_TAGS)):
                bio_b[i] -= scale * g_bb[i]
                bio_w[i] = [w - scale * g for w, g in zip(bio_w[i], g_bw[i], strict=True)]
    correct = 0
    for row in examples:
        x = intent_features(row.asr_text)
        logits = [
            intent_b[i] + sum(a * b for a, b in zip(intent_w[i], x, strict=True))
            for i in range(len(INTENTS))
        ]
        pred = max(range(len(INTENTS)), key=lambda i: logits[i])
        if INTENTS[pred] == row.intent:
            correct += 1
    accuracy = correct / max(1, len(examples))
    return {
        "encoder": "from_scratch",
        "intent_w": intent_w,
        "intent_b": intent_b,
        "bio_w": bio_w,
        "bio_b": bio_b,
        "intent_accuracy": accuracy,
        "rows": len(rows),
        "lr": lr,
        "plan_lr": PLAN_LR,
        "epochs": epochs,
        "batch": batch,
        "max_length": 128,
        "feature_dim": FEATURE_DIM,
        "ngram": NGRAM,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    parser.add_argument("--weights", type=Path, default=Path("models/weights/nlu_student.npz"))
    parser.add_argument("--metrics", type=Path, default=Path("docs/results/phase5_train.json"))
    args = parser.parse_args(argv)
    rows = load_rows(args.rows)
    result = train_student(rows)
    args.weights.parent.mkdir(parents=True, exist_ok=True)
    import numpy as np

    np.savez(
        args.weights,
        intent_w=np.asarray(result["intent_w"], dtype=np.float32),
        intent_b=np.asarray(result["intent_b"], dtype=np.float32),
        bio_w=np.asarray(result["bio_w"], dtype=np.float32),
        bio_b=np.asarray(result["bio_b"], dtype=np.float32),
        encoder=np.asarray("from_scratch"),
    )
    skip = {"intent_w", "intent_b", "bio_w", "bio_b"}
    public = {k: v for k, v in result.items() if k not in skip}
    public["training_data"] = str(args.rows).replace("\\", "/")
    public["training_data_sha256"] = hashlib.sha256(args.rows.read_bytes()).hexdigest()
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    raw_acc = public["intent_accuracy"]
    if not isinstance(raw_acc, float):
        raise TypeError("intent_accuracy must be float")
    print(f"encoder=from_scratch intent_accuracy={raw_acc:.4f} rows={public['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
