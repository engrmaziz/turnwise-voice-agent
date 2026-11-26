"""CPU p50 for the NLU student. Missing weights are blocked."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.harness import blocked_row, ok_row, time_callable
from evals.bench.schema import BenchRow
from models.nlu_pool import NluScorer
from server.config import Settings

TARGET_MS = 30.0


def measure_nlu_latency(settings: Settings) -> BenchRow:
    path = Path(settings.nlu_model_path.strip())
    if not settings.nlu_model_path.strip() or not path.is_file():
        return blocked_row("nlu_student", "nlu_model_path empty or missing")
    bio = path.with_name("nlu_bio.onnx")
    if not bio.is_file():
        return blocked_row("nlu_student", f"missing {bio.as_posix()}")
    scorer = NluScorer.load(
        path,
        bio,
        timeout_ms=max(settings.nlu_timeout_ms, 1000),
        feature_dim=settings.nlu_feature_dim,
        ngram=settings.nlu_ngram,
    )
    infer = scorer.infer_sync
    if infer is None:
        scorer.close()
        return blocked_row("nlu_student", "scorer has no infer_sync")

    def once() -> None:
        infer("book with Lan on Tuesday")

    try:
        p50, p95, _measured = time_callable(
            once, warmup=settings.bench_warmup, samples=settings.bench_samples
        )
    finally:
        scorer.close()
    extra: dict[str, object] = {"target_ms": TARGET_MS}
    extra["budget"] = "met" if p50 < TARGET_MS else "budget_missed"
    return ok_row("nlu_student", version="from_scratch", p50_ms=p50, p95_ms=p95, extra=extra)


def main() -> int:
    settings = Settings()
    if not settings.nlu_model_path.strip():
        settings = settings.model_copy(
            update={"nlu_model_path": "models/weights/nlu_intent.onnx"}
        )
    row = measure_nlu_latency(settings)
    out = Path("docs/results/phase5_nlu_latency.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(row.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(json.dumps(row.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
