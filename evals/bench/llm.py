"""LLM time-to-first-token. Grammar on and off are two rows."""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel

from evals.bench.harness import blocked_row, ok_row, percentile
from evals.bench.schema import BenchRow
from models.llm_client import ProposalSchema
from models.llm_ollama import OllamaError, list_models, time_first_token
from server.config import Settings

_PROMPT = (
    "You are a clinic receptionist. Return JSON for this turn: "
    "the caller said book tuesday at two thirty."
)


def measure_llm(settings: Settings) -> list[BenchRow]:
    ollama_rows = _ollama_rows(settings)
    if ollama_rows is not None:
        return ollama_rows
    binary = _llm_binary(settings)
    version = _version_from_binary(binary) if binary is not None else None
    reason = "missing_llm_binary" if binary is None else "model_layout_unpinned"
    return [
        blocked_row("llm.ttft.grammar_on", reason, version=version),
        blocked_row("llm.ttft.grammar_off", reason, version=version),
        blocked_row("llm.tokens_per_second.grammar_on", reason, version=version),
        blocked_row("llm.tokens_per_second.grammar_off", reason, version=version),
    ]


def _ollama_rows(settings: Settings) -> list[BenchRow] | None:
    if settings.llm_backend.strip() != "ollama":
        return None
    host = settings.llm_ollama_host.strip()
    model = settings.llm_ollama_model.strip()
    if not host or not model:
        return None
    timeout_s = max(settings.bench_timeout_s, 30.0)
    try:
        names = list_models(host, timeout_s=min(timeout_s, 5.0))
    except OllamaError:
        return None
    if model not in names and f"{model}:latest" not in names:
        return [
            blocked_row("llm.ttft.grammar_on", "ollama_model_missing", version=model),
            blocked_row("llm.ttft.grammar_off", "ollama_model_missing", version=model),
            blocked_row("llm.tokens_per_second.grammar_on", "ollama_model_missing", version=model),
            blocked_row("llm.tokens_per_second.grammar_off", "ollama_model_missing", version=model),
        ]
    try:
        time_first_token(host, model, _PROMPT, timeout_s=timeout_s, schema=ProposalSchema)
    except OllamaError as exc:
        reason = f"ollama_warmup_failed:{type(exc).__name__}"
        return [
            blocked_row("llm.ttft.grammar_on", reason, version=model),
            blocked_row("llm.ttft.grammar_off", reason, version=model),
            blocked_row("llm.tokens_per_second.grammar_on", reason, version=model),
            blocked_row("llm.tokens_per_second.grammar_off", reason, version=model),
        ]
    on_ttft, on_tps = _sample(settings, host, model, schema=ProposalSchema)
    off_ttft, off_tps = _sample(settings, host, model, schema=None)
    version = f"ollama:{model}"
    return [
        ok_row(
            "llm.ttft.grammar_on",
            version=version,
            p50_ms=percentile(on_ttft, 50.0),
            p95_ms=percentile(on_ttft, 95.0),
        ),
        ok_row(
            "llm.ttft.grammar_off",
            version=version,
            p50_ms=percentile(off_ttft, 50.0),
            p95_ms=percentile(off_ttft, 95.0),
        ),
        _tps_row("llm.tokens_per_second.grammar_on", version, on_tps),
        _tps_row("llm.tokens_per_second.grammar_off", version, off_tps),
    ]


def _sample(
    settings: Settings,
    host: str,
    model: str,
    *,
    schema: type[BaseModel] | None,
) -> tuple[list[float], list[float]]:
    timeout_s = max(settings.bench_timeout_s, 30.0)
    ttft: list[float] = []
    tps: list[float] = []
    total = settings.bench_warmup + settings.bench_samples
    for index in range(total):
        first_ms, _total_ms, count, eval_ns = time_first_token(
            host,
            model,
            _PROMPT,
            timeout_s=timeout_s,
            schema=schema,
        )
        if index >= settings.bench_warmup:
            ttft.append(first_ms)
            if eval_ns > 0 and count > 0:
                tps.append(count / (eval_ns / 1_000_000_000.0))
    return ttft, tps


def _tps_row(name: str, version: str, tps: list[float]) -> BenchRow:
    if not tps:
        return blocked_row(name, "ollama_no_eval_count", version=version)
    p50 = percentile(tps, 50.0)
    p95 = percentile(tps, 95.0)
    return ok_row(
        name,
        version=version,
        p50_ms=p50,
        p95_ms=p95,
        extra={"unit": "tokens_per_second"},
    )


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
