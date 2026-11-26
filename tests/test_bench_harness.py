"""Harness timer, blocked rows, and markdown that cannot invent milliseconds."""

from dataclasses import dataclass
from pathlib import Path

from evals.bench.adr import decide_tier, render_adr
from evals.bench.agreement import local_agreement_2
from evals.bench.asr import measure_asr
from evals.bench.fixture import write_tone_wav
from evals.bench.harness import (
    busy_wait,
    render_markdown,
    time_callable,
    time_worker,
    write_report,
)
from evals.bench.host import collect_host, probe_nvidia
from evals.bench.llm import measure_llm
from evals.bench.schema import BenchReport, BenchRow, HostInfo
from evals.bench.tts import measure_tts
from server.config import Settings


@dataclass(slots=True)
class SleepWorker:
    delay_s: float

    def describe(self) -> str:
        return f"sleep:{self.delay_s:.3f}s"

    def run_once(self) -> None:
        busy_wait(self.delay_s)


def test_ten_ms_sleep_p50_within_two_ms() -> None:
    p50, p95, samples = time_callable(lambda: busy_wait(0.01), warmup=2, samples=20)
    assert len(samples) == 20
    assert abs(p50 - 10.0) < 8.0
    assert p95 >= p50
    version, worker_p50, _p95, _ = time_worker(SleepWorker(0.01), warmup=2, samples=10)
    assert version == "sleep:0.010s"
    assert abs(worker_p50 - 10.0) < 8.0


def test_local_agreement_2_prefix() -> None:
    assert local_agreement_2("book with dr khan tomorrow", "book with dr khan today") == (
        "book with dr khan"
    )
    assert local_agreement_2("hello", "goodbye") == ""


def test_missing_binary_is_blocked(settings: Settings, tmp_path: Path) -> None:
    missing = tmp_path / "no-such-llama"
    configured = settings.model_copy(update={"bench_llm_command": str(missing)})
    rows = measure_llm(configured)
    assert rows
    assert all(row.status == "blocked" for row in rows)
    assert all(row.p50_ms is None and row.p95_ms is None for row in rows)
    asr_rows = measure_asr(configured, speech_wav=None)
    assert all(row.status == "blocked" for row in asr_rows)
    assert all(row.p50_ms is None for row in asr_rows)


def test_tts_gpu_not_present_when_nvidia_smi_missing(settings: Settings, tmp_path: Path) -> None:
    missing = str(tmp_path / "nvidia-smi")
    status, detail = probe_nvidia(missing)
    assert status == "not_present"
    assert detail is None
    configured = settings.model_copy(update={"tts_piper_onnx_path": str(tmp_path / "missing.onnx")})
    rows = measure_tts(configured, nvidia_smi=missing)
    cpu = next(row for row in rows if row.name == "tts.first_chunk.cpu")
    gpu = next(row for row in rows if row.name == "tts.first_chunk.gpu")
    assert cpu.status == "blocked"
    assert cpu.p50_ms is None
    assert gpu.status == "not_present"
    assert gpu.p50_ms is None


def test_markdown_and_adr_do_not_invent_ms(tmp_path: Path) -> None:
    report = _blocked_report(tmp_path)
    markdown = render_markdown(report)
    assert "| `asr.zipformer.finalize` | blocked |" in markdown
    assert "| blocked | blocked | no_speech_fixture |" in markdown
    write_report(report, json_path=tmp_path / "run.json", markdown_path=tmp_path / "out.md")
    written = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "Generated from the JSON sibling" in written
    tier, reason = decide_tier(report)
    assert tier == "blocked"
    assert "ASR finalize" in reason
    adr = render_adr(report)
    assert "**blocked**" in adr
    assert "- Date: 2026-11-26" in adr
    assert "ADR-003 stays Proposed" in adr


def test_tone_wav_is_ten_seconds_pcm16(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    write_tone_wav(path)
    size = path.stat().st_size
    assert size > 16000 * 2 * 10
    assert size < 16000 * 2 * 10 + 100


def test_collect_host_has_platform() -> None:
    host = collect_host(nvidia_smi=str(Path("no-such-nvidia-smi")))
    assert host.platform
    assert host.python
    assert host.nvidia_status == "not_present"


def _blocked_report(tmp_path: Path) -> BenchReport:
    return BenchReport(
        started_utc="20261126T000000Z",
        command=["python", "-m", "evals.bench"],
        host=HostInfo(
            platform="test",
            python="3.11.9",
            cpu_count=8,
            ram_gb=16.0,
            nvidia_smi=None,
            nvidia_status="not_present",
        ),
        warmup=5,
        samples=20,
        fixture_text="The north wind and the sun were disputing which was the stronger.",
        fixture_license="public-domain",
        fixture_audio="tone_placeholder_not_speech",
        rows=[
            BenchRow(name="asr.zipformer.finalize", status="blocked", reason="no_speech_fixture"),
            BenchRow(name="llm.ttft.grammar_on", status="blocked", reason="missing_llm_binary"),
            BenchRow(name="tts.first_chunk.cpu", status="blocked", reason="missing_tts"),
            BenchRow(name="tts.first_chunk.gpu", status="not_present", reason="nvidia_smi_failed"),
        ],
        json_path=(tmp_path / "run.json").as_posix(),
        markdown_path=(tmp_path / "out.md").as_posix(),
        adr_path=(tmp_path / "ADR.md").as_posix(),
    )
