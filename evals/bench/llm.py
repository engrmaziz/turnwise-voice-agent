"""LLM time-to-first-token. Grammar on and off are two rows."""

from __future__ import annotations

import shutil
from pathlib import Path

from evals.bench.harness import blocked_row
from evals.bench.schema import BenchRow
from server.config import Settings


def measure_llm(settings: Settings) -> list[BenchRow]:
    binary = _llm_binary(settings)
    version = _version_from_binary(binary) if binary is not None else None
    reason = "missing_llm_binary" if binary is None else "model_layout_unpinned"
    return [
        blocked_row("llm.ttft.grammar_on", reason, version=version),
        blocked_row("llm.ttft.grammar_off", reason, version=version),
        blocked_row("llm.tokens_per_second.grammar_on", reason, version=version),
        blocked_row("llm.tokens_per_second.grammar_off", reason, version=version),
    ]


def _llm_binary(settings: Settings) -> str | None:
    configured = settings.bench_llm_command.strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return configured
        return shutil.which(configured)
    for name in ("llama-cli", "llama-server", "llama.cpp"):
        found = shutil.which(name)
        if found is not None:
            return found
    return None


def _version_from_binary(binary: str) -> str | None:
    from subprocess import TimeoutExpired, run

    try:
        proc = run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr).strip().splitlines()
    if not text:
        return None
    return text[0][:200]
