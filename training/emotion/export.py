"""Export an emotion ONNX. Writes skipped until train.py produces a checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATUS_PATH = Path("training/emotion/export_status.json")
CHECKPOINT = Path("training/emotion/checkpoint")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--out", type=Path, default=Path("models/weights/emotion.onnx"))
    args = parser.parse_args(argv)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not args.checkpoint.exists():
        payload = {"status": "skipped", "reason": "no_checkpoint"}
        STATUS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write("skipped: no emotion checkpoint\n")
        return 0
    payload = {"status": "skipped", "reason": "export_unwired", "checkpoint": str(args.checkpoint)}
    STATUS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write("skipped: export is unwired until T8.1.3 lands weights\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
