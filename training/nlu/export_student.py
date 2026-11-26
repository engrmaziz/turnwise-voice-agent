"""Export the joint student to ONNX. INT8 when quantization succeeds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from nlp.nlu_features import FEATURE_DIM
from nlp.nlu_vocab import BIO_TAGS, INTENTS


def export_student(
    weights_path: Path,
    onnx_dir: Path,
    *,
    data_path: Path,
) -> dict[str, object]:
    import numpy as np

    packed = np.load(weights_path)
    intent_w = np.asarray(packed["intent_w"], dtype=np.float32).T
    intent_b = np.asarray(packed["intent_b"], dtype=np.float32)
    bio_w = np.asarray(packed["bio_w"], dtype=np.float32).T
    bio_b = np.asarray(packed["bio_b"], dtype=np.float32)
    onnx_dir.mkdir(parents=True, exist_ok=True)
    intent_path = onnx_dir / "nlu_intent.onnx"
    bio_path = onnx_dir / "nlu_bio.onnx"
    _save_linear(intent_path, intent_w, intent_b, "intent")
    _save_linear(bio_path, bio_w, bio_b, "bio")
    int8_ok = _quantize(intent_path) and _quantize(bio_path)
    if int8_ok:
        sized = (
            intent_path.with_name(intent_path.stem + ".int8.onnx"),
            bio_path.with_name(bio_path.stem + ".int8.onnx"),
        )
    else:
        sized = (intent_path, bio_path)
    size_mb = (sized[0].stat().st_size + sized[1].stat().st_size) / (1024 * 1024)
    card = {
        "encoder": "from_scratch",
        "intents": list(INTENTS),
        "bio_tags": list(BIO_TAGS),
        "feature_dim": FEATURE_DIM,
        "intent_onnx": str(intent_path).replace("\\", "/"),
        "bio_onnx": str(bio_path).replace("\\", "/"),
        "int8": int8_ok,
        "size_mb": size_mb,
        "training_data": str(data_path).replace("\\", "/"),
        "training_data_sha256": _sha256(data_path) if data_path.is_file() else "",
    }
    card_path = onnx_dir / "nlu_student.card.json"
    card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in card.items() if k != "bio_tags"}))
    return card


def _save_linear(path: Path, weights: object, bias: object, name: str) -> None:
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    w = np.asarray(weights, dtype=np.float32)
    b = np.asarray(bias, dtype=np.float32)
    x = helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, FEATURE_DIM])
    y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, [1, int(b.shape[0])])
    graph = helper.make_graph(
        [
            helper.make_node("Gemm", ["X", "W", "B"], ["L"]),
            helper.make_node("Softmax", ["L"], ["Y"], axis=1),
        ],
        name,
        [x],
        [y],
        [numpy_helper.from_array(w, name="W"), numpy_helper.from_array(b, name="B")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
    onnx.save(model, path)


def _quantize(path: Path) -> bool:
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        out = path.with_name(path.stem + ".int8.onnx")
        quantize_dynamic(str(path), str(out), weight_type=QuantType.QInt8)
    except Exception as exc:
        print(f"int8_error={type(exc).__name__}: {exc}")
        return False
    else:
        return out.is_file()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=Path("models/weights/nlu_student.npz"))
    parser.add_argument("--onnx-dir", type=Path, default=Path("models/weights"))
    parser.add_argument("--data", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    args = parser.parse_args(argv)
    if not args.weights.is_file():
        raise SystemExit(f"missing weights: {args.weights}")
    export_student(args.weights, args.onnx_dir, data_path=args.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
