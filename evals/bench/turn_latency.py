"""CPU p50 for the turn-completeness ONNX scorer. Missing weights are blocked."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.harness import blocked_row, ok_row, time_callable
from evals.bench.schema import BenchRow
from models.onnx_pool import TurnScorer
from models.turn_features import FEATURE_DIM, NGRAM
from server.config import Settings

TARGET_MS = 10.0


def measure_turn_latency(settings: Settings) -> BenchRow:
    path = Path(settings.turn_onnx_path)
    if not path.is_file():
        return blocked_row("turn_complete", f"missing {path.as_posix()}")
    scorer = TurnScorer.load(
        path,
        timeout_ms=max(settings.turn_timeout_ms, 1000),
        feature_dim=settings.turn_feature_dim or FEATURE_DIM,
        ngram=settings.turn_ngram or NGRAM,
    )
    infer = scorer.infer_sync
    if infer is None:
        scorer.close()
        return blocked_row("turn_complete", "scorer has no infer_sync")

    def once() -> None:
        infer("book tuesday at two thirty", "none")

    try:
        p50, p95, _measured = time_callable(
            once,
            warmup=settings.bench_warmup,
            samples=settings.bench_samples,
        )
    finally:
        scorer.close()
    extra: dict[str, object] = {"target_ms": TARGET_MS}
    if p50 >= TARGET_MS:
        extra["budget"] = "budget_missed"
    else:
        extra["budget"] = "met"
    return ok_row(
        "turn_complete",
        version="from_scratch",
        p50_ms=p50,
        p95_ms=p95,
        extra=extra,
    )


def write_turn_latency(row: BenchRow, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(row.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main() -> int:
    from server.config import Settings

    settings = Settings()
    row = measure_turn_latency(settings)
    out = Path("docs/results/phase4_turn_latency.json")
    write_turn_latency(row, out)
    print(json.dumps(row.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
