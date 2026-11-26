"""Export the linear turn model to ONNX. INT8 when onnxruntime can quantize."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from models.turn_features import FEATURE_DIM, NGRAM


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def export_onnx(
    weights_path: Path,
    onnx_path: Path,
    *,
    fixtures_path: Path,
    latency_json: Path,
) -> dict[str, object]:
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    packed = np.load(weights_path)
    weights = np.asarray(packed["weights"], dtype=np.float32).reshape(FEATURE_DIM, 1)
    bias = np.asarray(packed["bias"], dtype=np.float32).reshape(1)
    x = helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, FEATURE_DIM])
    y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, [1, 1])
    graph = helper.make_graph(
        [
            helper.make_node("Gemm", ["X", "W", "B"], ["L"]),
            helper.make_node("Sigmoid", ["L"], ["Y"]),
        ],
        "turn_complete",
        [x],
        [y],
        [
            numpy_helper.from_array(weights, name="W"),
            numpy_helper.from_array(bias, name="B"),
        ],
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 13)],
        ir_version=8,
    )
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, onnx_path)
    int8_path = onnx_path.with_name(onnx_path.stem + ".int8.onnx")
    quantized = False
    quant_error = ""
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(str(onnx_path), str(int8_path), weight_type=QuantType.QInt8)
        quantized = int8_path.is_file()
    except Exception as exc:
        quant_error = f"{type(exc).__name__}: {exc}"
    card = {
        "encoder": "from_scratch",
        "training_data": str(fixtures_path).replace("\\", "/"),
        "training_data_sha256": _file_sha256(fixtures_path) if fixtures_path.is_file() else "",
        "onnx_path": str(onnx_path).replace("\\", "/"),
        "int8_path": str(int8_path).replace("\\", "/") if quantized else "",
        "int8": quantized,
        "int8_error": quant_error,
        "feature_dim": FEATURE_DIM,
        "ngram": NGRAM,
        "metric_names": [
            "turnwise_turn_model_seconds",
            "turnwise_turn_model_timeouts_total",
        ],
        "latency_json": str(latency_json).replace("\\", "/"),
    }
    card_path = onnx_path.with_suffix(".card.json")
    card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(card))
    return card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=Path("models/weights/turn_complete.npz"))
    parser.add_argument("--onnx", type=Path, default=Path("models/weights/turn_complete.onnx"))
    parser.add_argument("--fixtures", type=Path, default=Path("training/turn/fixtures.txt"))
    parser.add_argument(
        "--latency-json",
        type=Path,
        default=Path("docs/results/phase4_turn_latency.json"),
    )
    args = parser.parse_args(argv)
    if not args.weights.is_file():
        raise SystemExit(f"missing weights: {args.weights}")
    export_onnx(
        args.weights,
        args.onnx,
        fixtures_path=args.fixtures,
        latency_json=args.latency_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
