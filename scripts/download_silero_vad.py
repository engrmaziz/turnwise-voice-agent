"""Fetch Silero VAD ONNX into models/weights/. Weights stay gitignored."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
DEST = Path("models/weights/silero_vad.onnx")


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        payload = response.read()
    if len(payload) < 10_000:
        sys.stderr.write("download too small to be an ONNX file\n")
        return 1
    DEST.write_bytes(payload)
    sys.stdout.write(f"wrote {DEST} bytes={len(payload)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
