"""Tiny from_scratch linear trainer. Full corpus train is mark bench."""

from pathlib import Path

from models.turn_features import hashed_vector
from training.turn.build_truncation import truncation_rows
from training.turn.export import export_onnx
from training.turn.train import train_linear


def test_linear_train_on_tiny_set() -> None:
    sentences = [
        "I need to book with Dr. Avery Lang on Wednesday at two thirty",
        "The sun rose over the river at dawn",
        "Cancel my appointment with Dr. Helen Voss on Friday at ten",
    ]
    features: list[list[float]] = []
    labels: list[float] = []
    for sentence in sentences:
        for row in truncation_rows(sentence):
            features.append(hashed_vector(str(row["text"]), str(row["slot"])))
            labels.append(float(row["complete"]))
    weights, bias, accuracy = train_linear(features, labels, epochs=2, batch=4)
    assert len(weights) == len(features[0])
    assert 0.0 <= accuracy <= 1.0
    assert abs(bias) + sum(abs(w) for w in weights) > 0.0


def test_export_onnx_roundtrip(tmp_path: Path) -> None:
    import numpy as np

    weights_path = tmp_path / "turn.npz"
    np.savez(
        weights_path,
        weights=np.zeros(256, dtype=np.float32),
        bias=np.zeros(1, dtype=np.float32),
    )
    fixtures = tmp_path / "fixtures.txt"
    fixtures.write_text("# License: CC0-1.0\nhello world\n", encoding="utf-8")
    onnx_path = tmp_path / "turn.onnx"
    card = export_onnx(
        weights_path,
        onnx_path,
        fixtures_path=fixtures,
        latency_json=tmp_path / "lat.json",
    )
    assert onnx_path.is_file()
    assert card["encoder"] == "from_scratch"
