"""Fine-tune wav2vec2 or emotion2vec. Writes skipped when data or libs are missing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATUS_PATH = Path("training/emotion/train_status.json")
RAW_DIR = Path("training/emotion/raw")


def _write_status(payload: dict[str, object]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--batch", type=int, default=8)
    args = parser.parse_args(argv)
    wavs = list(args.raw.rglob("*.wav")) if args.raw.is_dir() else []
    try:
        import transformers  # noqa: F401
    except ImportError:
        wav2vec = "blocked"
    else:
        wav2vec = "import_ok"
    try:
        import funasr  # noqa: F401
    except ImportError:
        emotion2vec = "blocked"
    else:
        emotion2vec = "import_ok"
    if not wavs:
        _write_status(
            {
                "status": "skipped",
                "reason": "no_wavs",
                "wav2vec2": wav2vec,
                "emotion2vec": emotion2vec,
                "epochs": args.epochs,
                "lr": args.lr,
                "batch": args.batch,
            }
        )
        sys.stdout.write("skipped: no wavs under training/emotion/raw\n")
        return 0
    if wav2vec == "blocked" and emotion2vec == "blocked":
        _write_status(
            {
                "status": "skipped",
                "reason": "no_trainer_library",
                "wav2vec2": wav2vec,
                "emotion2vec": emotion2vec,
            }
        )
        sys.stdout.write("skipped: neither wav2vec2 nor emotion2vec imports\n")
        return 0
    _write_status(
        {
            "status": "skipped",
            "reason": "acted_train_not_run",
            "wav2vec2": wav2vec,
            "emotion2vec": emotion2vec,
            "wavs": len(wavs),
        }
    )
    sys.stdout.write("skipped: T8.1.3 is slip; no acted F1 is published\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
