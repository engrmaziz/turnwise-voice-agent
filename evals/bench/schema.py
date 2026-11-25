"""JSON log for one bench run. Markdown and ADR-004 are rendered from this."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RowStatus = Literal["ok", "blocked", "not_present"]


class HostInfo(BaseModel):
    platform: str
    python: str
    cpu_count: int
    ram_gb: float | None
    nvidia_smi: str | None
    nvidia_status: Literal["present", "not_present"]


class BenchRow(BaseModel):
    name: str
    status: RowStatus
    version: str | None = None
    reason: str | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BenchReport(BaseModel):
    schema_version: int = 1
    started_utc: str
    command: list[str]
    host: HostInfo
    warmup: int
    samples: int
    fixture_text: str
    fixture_license: str
    fixture_audio: str
    rows: list[BenchRow]
    json_path: str
    markdown_path: str
    adr_path: str
