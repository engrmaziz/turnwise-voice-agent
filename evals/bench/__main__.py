"""``python -m evals.bench`` writes JSON, ``docs/benchmarks.md``, and ADR-004."""

from __future__ import annotations

import sys

import structlog

from evals.bench.suite import run_suite
from server.config import get_settings
from server.log_setup import configure_logging
from server.pii import PiiRedactor

_LOG = structlog.get_logger("evals.bench")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    settings = get_settings()
    configure_logging(settings, PiiRedactor(settings))
    report = run_suite(settings, command=args)
    _LOG.info(
        "bench_written",
        json_path=report.json_path,
        markdown_path=report.markdown_path,
        adr_path=report.adr_path,
        rows=len(report.rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
