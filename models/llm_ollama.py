"""Ollama HTTP generate. JSON schema is passed as ``format``, never regex-scraped."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel


class OllamaError(RuntimeError):
    """Host unreachable, empty body, or a non-JSON generate payload."""


def list_models(host: str, *, timeout_s: float) -> tuple[str, ...]:
    payload = _request(f"{host.rstrip('/')}/api/tags", None, timeout_s)
    models = payload.get("models")
    if not isinstance(models, list):
        return ()
    names: list[str] = []
    for item in models:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return tuple(names)


def generate(
    host: str,
    model: str,
    prompt: str,
    *,
    timeout_s: float,
    schema: type[BaseModel] | None = None,
    num_predict: int = 256,
) -> str:
    body: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    if schema is not None:
        body["format"] = schema.model_json_schema()
    payload = _request(f"{host.rstrip('/')}/api/generate", body, timeout_s)
    text = payload.get("response")
    if not isinstance(text, str) or not text.strip():
        raise OllamaError("empty ollama response")
    return text


def time_first_token(
    host: str,
    model: str,
    prompt: str,
    *,
    timeout_s: float,
    schema: type[BaseModel] | None = None,
    num_predict: int = 64,
) -> tuple[float, float, int, int]:
    """Return (ttft_ms, total_ms, eval_count). Stream so TTFT is first non-empty chunk."""
    body: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "think": False,
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    if schema is not None:
        body["format"] = schema.model_json_schema()
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_ms: float | None = None
    eval_count = 0
    eval_duration_ns = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("response")
                if first_ms is None and isinstance(piece, str) and piece:
                    first_ms = (time.perf_counter() - started) * 1000.0
                if chunk.get("done") is True:
                    count = chunk.get("eval_count")
                    duration = chunk.get("eval_duration")
                    if isinstance(count, int):
                        eval_count = count
                    if isinstance(duration, int):
                        eval_duration_ns = duration
                    break
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise OllamaError(f"ollama stream failed: {type(exc).__name__}") from exc
    total_ms = (time.perf_counter() - started) * 1000.0
    if first_ms is None:
        raise OllamaError("empty ollama stream")
    return first_ms, total_ms, eval_count, eval_duration_ns


def _request(url: str, body: dict[str, object] | None, timeout_s: float) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode())
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise OllamaError(f"ollama request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise OllamaError("ollama payload must be an object")
    return payload
