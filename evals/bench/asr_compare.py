"""Zipformer versus Whisper+LA-2 on the same fixtures. Missing weights stay blocked."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

from evals.bench.harness import ok_row, percentile
from evals.bench.schema import BenchRow
from models.asr_zipformer import decode_utterance, load_zipformer_recognizer, warmup_recognizer
from models.tts_pool import TtsError, TtsPool
from server.config import Settings

FIXTURES = (
    "book tuesday at two thirty",
    "cancel my appointment with doctor lang",
    "reschedule to next wednesday",
    "I need a checkup tomorrow",
    "is doctor okonkwo available friday",
    "the day after tomorrow at three o'clock",
    "speak to a human please",
    "what are your hours",
    "chest pain and cannot breathe",
    "appointment for march third",
    "phone number five five five one two one two",
    "see doctor qadir this thursday",
    "book with doctor voss next monday",
    "cancel friday morning",
    "follow up with doctor chaudhry",
    "is the clinic open today",
    "need blood work next tuesday",
    "doctor hale after lunch",
    "move it to this saturday",
    "new patient with doctor sorenson",
)

SynthFn = Callable[[str], bytes]


def measure_asr_compare(settings: Settings) -> list[BenchRow]:
    """Twenty Piper-spoken fixtures when Zipformer weights exist.

    Whisper uses the pinned dir or a Hugging Face hub snapshot already on disk.
    """
    if len(FIXTURES) != 20:
        raise RuntimeError("phase 3 compare set must be 20 fixtures")
    zip_rows = _zipformer_rows(settings)
    return [*zip_rows, *_whisper_rows(settings)]


def write_compare_json(rows: list[BenchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.model_dump() for row in rows]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def zipformer_unavailable_reason(settings: Settings) -> str | None:
    if importlib.util.find_spec("sherpa_onnx") is None:
        return "weights_unpinned"
    encoder = Path(settings.asr_zipformer_encoder_path)
    decoder = Path(settings.asr_zipformer_decoder_path)
    joiner = Path(settings.asr_zipformer_joiner_path)
    tokens = Path(settings.asr_zipformer_tokens_path)
    if not all(path.is_file() for path in (encoder, decoder, joiner, tokens)):
        return "weights_unpinned"
    return None


def load_piper_synth(settings: Settings) -> SynthFn | None:
    if importlib.util.find_spec("piper") is None:
        return None
    onnx = Path(settings.tts_piper_onnx_path)
    if not onnx.is_file():
        return None
    config_raw = settings.tts_piper_config_path.strip()
    config_path = Path(config_raw) if config_raw else None
    try:
        pool = TtsPool.piper(
            onnx_path=onnx,
            config_path=config_path,
            timeout_ms=max(1, int(settings.bench_timeout_s * 1000)),
            output_hz=settings.ws_sample_rate_hz,
        )
    except (ImportError, OSError, ValueError, RuntimeError, TtsError):
        return None
    synth = pool.synth_sync
    if synth is None:
        pool.close()
        return None

    def run(text: str) -> bytes:
        return synth(text, settings.tts_voice, settings.tts_speed)

    return run


def _zipformer_rows(settings: Settings) -> list[BenchRow]:
    reason = zipformer_unavailable_reason(settings)
    if reason is not None:
        return [
            _blocked("asr.compare.zipformer.finalize", reason),
            _blocked("asr.compare.zipformer.stabilization", reason),
        ]
    synth = load_piper_synth(settings)
    if synth is None:
        return [
            _blocked("asr.compare.zipformer.finalize", "tts_blocked"),
            _blocked("asr.compare.zipformer.stabilization", "tts_blocked"),
        ]
    try:
        recognizer = load_zipformer_recognizer(
            encoder=Path(settings.asr_zipformer_encoder_path),
            decoder=Path(settings.asr_zipformer_decoder_path),
            joiner=Path(settings.asr_zipformer_joiner_path),
            tokens=Path(settings.asr_zipformer_tokens_path),
            sample_rate=settings.ws_sample_rate_hz,
            hotword_score=settings.hotword_score,
            bpe_vocab=Path(settings.asr_zipformer_bpe_vocab_path),
            bpe_model=Path(settings.asr_zipformer_bpe_model_path),
        )
        warmup_recognizer(recognizer, settings.ws_sample_rate_hz)
        drains: list[float] = []
        texts: list[str] = []
        for phrase in FIXTURES:
            pcm = synth(phrase)
            hypo, drain_ms = decode_utterance(
                recognizer,
                pcm,
                settings.ws_sample_rate_hz,
            )
            drains.append(drain_ms)
            texts.append(hypo.text)
    except (OSError, ValueError, RuntimeError, TtsError, ImportError) as exc:
        failed = f"zipformer_failed:{type(exc).__name__}"
        return [
            _blocked("asr.compare.zipformer.finalize", failed),
            _blocked("asr.compare.zipformer.stabilization", failed),
        ]
    extra = _extra(drains, texts)
    version = _zipformer_version()
    p50 = percentile(drains, 50.0)
    p95 = percentile(drains, 95.0)
    return [
        ok_row(
            "asr.compare.zipformer.finalize",
            version=version,
            p50_ms=p50,
            p95_ms=p95,
            extra=extra,
        ),
        ok_row(
            "asr.compare.zipformer.stabilization",
            version=version,
            p50_ms=p50,
            p95_ms=p95,
            extra=extra,
        ),
    ]


def _whisper_rows(settings: Settings) -> list[BenchRow]:
    from models.asr_whisper import (
        local_agreement_delay_ms,
        resolve_whisper_dir,
        transcribe_pcm16,
        whisper_unavailable_reason,
    )

    extra = _extra([], [])
    blocked = whisper_unavailable_reason(settings)
    if blocked is not None:
        return [
            _blocked("asr.compare.whisper_la2.finalize", blocked, extra=extra),
            _blocked("asr.compare.whisper_la2.stabilization", blocked, extra=extra),
        ]
    synth = load_piper_synth(settings)
    if synth is None:
        return [
            _blocked("asr.compare.whisper_la2.finalize", "tts_blocked", extra=extra),
            _blocked("asr.compare.whisper_la2.stabilization", "tts_blocked", extra=extra),
        ]
    model_dir = resolve_whisper_dir(settings)
    if model_dir is None:
        return [
            _blocked("asr.compare.whisper_la2.finalize", "weights_unpinned", extra=extra),
            _blocked("asr.compare.whisper_la2.stabilization", "weights_unpinned", extra=extra),
        ]
    try:
        drains: list[float] = []
        delays: list[float] = []
        texts: list[str] = []
        for phrase in FIXTURES:
            pcm = synth(phrase)
            _text, drain_ms = transcribe_pcm16(
                pcm,
                settings.ws_sample_rate_hz,
                model_dir=model_dir,
                dst_hz=settings.ws_sample_rate_hz,
            )
            _hypo, delay_ms, _stable = local_agreement_delay_ms(
                pcm,
                settings.ws_sample_rate_hz,
                model_dir=model_dir,
                dst_hz=settings.ws_sample_rate_hz,
            )
            drains.append(drain_ms)
            delays.append(delay_ms)
            texts.append(_text)
    except (OSError, ValueError, RuntimeError, TtsError, ImportError) as exc:
        failed = f"whisper_failed:{type(exc).__name__}"
        return [
            _blocked("asr.compare.whisper_la2.finalize", failed, extra=extra),
            _blocked("asr.compare.whisper_la2.stabilization", failed, extra=extra),
        ]
    extra = _extra(drains, texts)
    extra["stabilization_delay_ms_p50"] = percentile(delays, 50.0)
    extra["stabilization_delay_ms_p95"] = percentile(delays, 95.0)
    extra["delay_basis"] = "la2_after_last_window"
    version = _whisper_version()
    return [
        ok_row(
            "asr.compare.whisper_la2.finalize",
            version=version,
            p50_ms=percentile(drains, 50.0),
            p95_ms=percentile(drains, 95.0),
            extra=extra,
        ),
        ok_row(
            "asr.compare.whisper_la2.stabilization",
            version=version,
            p50_ms=percentile(delays, 50.0),
            p95_ms=percentile(delays, 95.0),
            extra=extra,
        ),
    ]


def _whisper_version() -> str:
    version = "unknown"
    try:
        import faster_whisper

        raw = getattr(faster_whisper, "__version__", None)
        if raw is not None:
            version = str(raw)
    except ImportError:
        version = "unknown"
    return f"{version};faster-whisper;cpu-int8"


def _blocked(name: str, reason: str, *, extra: dict[str, object] | None = None) -> BenchRow:
    payload = extra if extra is not None else _extra([], [])
    return BenchRow(name=name, status="blocked", reason=reason, extra=payload)


def _extra(drains: list[float], texts: list[str]) -> dict[str, object]:
    p50 = percentile(drains, 50.0) if drains else None
    p95 = percentile(drains, 95.0) if drains else None
    return {
        "fixtures": len(FIXTURES),
        "decoded": len(texts),
        "stabilization_delay_ms_p50": p50,
        "stabilization_delay_ms_p95": p95,
        "delay_basis": "utterance_end",
        "transcripts": texts,
    }


def _zipformer_version() -> str:
    version = "unknown"
    try:
        import sherpa_onnx

        raw = getattr(sherpa_onnx, "__version__", None)
        if raw is not None:
            version = str(raw)
    except ImportError:
        version = "unknown"
    return f"{version};zipformer2;int8;en-2023-06-26"
