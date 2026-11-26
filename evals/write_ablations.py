"""Write the five ablation JSON objects into one file."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.ablate_asr import run as asr
from evals.ablate_bias import run as bias
from evals.ablate_endpoint import run as endpoint
from evals.ablate_fsm import run as fsm
from evals.ablate_nlu import run as nlu
from server.config import Settings


def main() -> int:
    settings = Settings()
    root = Path("docs/results")
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        payload = {
            "endpoint": endpoint(settings=settings, out=scratch / "ablate_endpoint.json"),
            "bias": bias(settings=settings, out=scratch / "ablate_bias.json"),
            "nlu": nlu(settings=settings, out=scratch / "ablate_nlu.json"),
            "fsm": fsm(settings=settings, out=scratch / "ablate_fsm.json"),
            "asr": asr(settings=settings, out=scratch / "ablate_asr.json"),
        }
    (root / "phase9_ablations.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
