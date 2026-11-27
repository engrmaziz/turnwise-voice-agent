"""Realtime subset. Virtual-clock numbers stay skipped (ADR-012)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from evals.realtime_driver import run_pcm_sessions
from server.config import Settings


def run_realtime(*, n: int, out: Path, settings: Settings) -> dict[str, object]:
    """Do not invent TTFA. Virtual-clock numbers must not be labeled realtime."""
    if settings.eval_time_scale != 1.0:
        payload: dict[str, object] = {
            "status": "skipped",
            "reason": "eval_time_scale is virtual",
            "n": 0,
            "requested_n": n,
            "clock": "realtime",
            "product_quote": False,
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    measured = asyncio.run(
        run_pcm_sessions(
            settings,
            n=n,
            pace_s=settings.ws_frame_ms / 1000.0,
        )
    )
    acked_raw = measured.get("sessions_acked")
    acked = acked_raw if isinstance(acked_raw, int) else 0
    samples_raw = measured.get("ttfa_samples")
    samples = samples_raw if isinstance(samples_raw, int) else 0
    payload = {
        "status": "ok" if acked == n and samples >= n else "miss",
        "reason": "play_ack_histogram",
        "n": acked,
        "requested_n": n,
        "clock": "realtime",
        "pace_s": settings.ws_frame_ms / 1000.0,
        "vad": "energy_fallback",
        "product_quote": False,
        **measured,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase9_realtime.json"))
    parser.add_argument("--n", type=int, default=None)
    args = parser.parse_args(argv)
    settings = Settings(
        eval_time_scale=1.0,
        otel_enabled=False,
        vad_onnx_path="models/weights/missing.onnx",
        turn_model_enabled=False,
    )
    requested = args.n if args.n is not None else settings.eval_realtime_n
    run_realtime(n=requested, out=args.out, settings=settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
