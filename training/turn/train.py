"""Train a hashed-ngram linear turn-completeness classifier.

STARTING POINT from plan T4.2.2 (transformer-scale): lr=2e-5, epochs=3,
batch=32, max length=64. This file trains a from_scratch linear model, so
TRAIN_LR is 0.1 so the weights move. Do not claim a transformer.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from models.turn_features import FEATURE_DIM, MAX_LENGTH, NGRAM, hashed_vector
from training.turn.build_truncation import iter_rows, load_fixtures

# Plan T4.2.2 STARTING POINT (unused for this linear model; kept as the record).
PLAN_LR = 2e-5
PLAN_EPOCHS = 3
PLAN_BATCH = 32
PLAN_MAX_LENGTH = MAX_LENGTH

TRAIN_LR = 0.1
TRAIN_EPOCHS = 3
TRAIN_BATCH = 32
HOLD_FRACTION = 0.2
SEED = 7


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


def _load_xy(fixtures: Path) -> tuple[list[list[float]], list[float]]:
    rows = list(iter_rows(load_fixtures(fixtures)))
    features = [
        hashed_vector(str(row["text"]), str(row["slot"]), dim=FEATURE_DIM, ngram=NGRAM)
        for row in rows
    ]
    labels = [float(row["complete"]) for row in rows]
    return features, labels


def train_linear(
    features: list[list[float]],
    labels: list[float],
    *,
    lr: float = TRAIN_LR,
    epochs: int = TRAIN_EPOCHS,
    batch: int = TRAIN_BATCH,
    seed: int = SEED,
) -> tuple[list[float], float, float]:
    """Return (weights, bias, held-out accuracy)."""
    rng = random.Random(seed)
    paired = list(zip(features, labels, strict=True))
    rng.shuffle(paired)
    hold_n = max(1, int(len(paired) * HOLD_FRACTION))
    hold = paired[:hold_n]
    train = paired[hold_n:]
    dim = len(features[0])
    weights = [0.0] * dim
    bias = 0.0
    for _ in range(epochs):
        rng.shuffle(train)
        for start in range(0, len(train), batch):
            chunk = train[start : start + batch]
            grad_w = [0.0] * dim
            grad_b = 0.0
            for vec, label in chunk:
                logit = bias + sum(
                    weight * value for weight, value in zip(weights, vec, strict=True)
                )
                pred = _sigmoid(logit)
                err = pred - label
                for i, value in enumerate(vec):
                    grad_w[i] += err * value
                grad_b += err
            scale = lr / max(1, len(chunk))
            weights = [weight - scale * g for weight, g in zip(weights, grad_w, strict=True)]
            bias -= scale * grad_b
    correct = 0
    for vec, label in hold:
        logit = bias + sum(weight * value for weight, value in zip(weights, vec, strict=True))
        pred = 1.0 if _sigmoid(logit) >= 0.5 else 0.0
        if pred == label:
            correct += 1
    accuracy = correct / max(1, len(hold))
    return weights, bias, accuracy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("training/turn/fixtures.txt"))
    parser.add_argument("--weights", type=Path, default=Path("models/weights/turn_complete.npz"))
    parser.add_argument("--metrics", type=Path, default=Path("docs/results/phase4_train.json"))
    args = parser.parse_args(argv)
    features, labels = _load_xy(args.fixtures)
    weights, bias, accuracy = train_linear(features, labels)
    args.weights.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit("numpy is required to write weights") from exc
    np.savez(
        args.weights,
        weights=np.asarray(weights, dtype=np.float32),
        bias=np.asarray([bias], dtype=np.float32),
        dim=FEATURE_DIM,
        ngram=NGRAM,
        encoder="from_scratch",
    )
    payload = {
        "encoder": "from_scratch",
        "held_out_accuracy": accuracy,
        "rows": len(features),
        "lr": TRAIN_LR,
        "plan_lr": PLAN_LR,
        "epochs": TRAIN_EPOCHS,
        "batch": TRAIN_BATCH,
        "max_length": PLAN_MAX_LENGTH,
        "feature_dim": FEATURE_DIM,
    }
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"held_out_accuracy={accuracy:.4f} rows={len(features)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
