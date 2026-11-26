"""Entity WER with hotword bias on and off. Missing TTS or hotword API is not a number."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.asr_compare import load_piper_synth, zipformer_unavailable_reason
from evals.bench.harness import blocked_row
from evals.bench.schema import BenchRow
from models.asr_zipformer import decode_utterance, load_zipformer_recognizer, warmup_recognizer
from models.tts_pool import TtsError
from nlp.hotwords import load_roster
from server.config import Settings


def measure_entity_wer(settings: Settings, *, supports_hotwords: bool) -> list[BenchRow]:
    """Synthesize the roster through Piper. Blocked TTS is not text-only WER."""
    roster = load_roster(Path(settings.doctor_roster_path))
    if len(roster) < 15:
        raise RuntimeError("roster must have at least 15 invented names")
    names = list(roster) + list(roster)[:15]
    names = names[:30]
    off = _bias_off_row(settings, names)
    # Greedy Zipformer has no hotword API. The stub does; this bench measures Zipformer.
    _ = supports_hotwords
    return [off, blocked_row("asr.entity_wer.bias_on", "unsupported")]


def write_entity_json(rows: list[BenchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([row.model_dump() for row in rows], indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")


def _bias_off_row(settings: Settings, names: list[str]) -> BenchRow:
    blocked = zipformer_unavailable_reason(settings)
    if blocked is not None:
        return blocked_row("asr.entity_wer.bias_off", blocked)
    synth = load_piper_synth(settings)
    if synth is None:
        return blocked_row("asr.entity_wer.bias_off", "tts_blocked")
    try:
        recognizer = load_zipformer_recognizer(
            encoder=Path(settings.asr_zipformer_encoder_path),
            decoder=Path(settings.asr_zipformer_decoder_path),
            joiner=Path(settings.asr_zipformer_joiner_path),
            tokens=Path(settings.asr_zipformer_tokens_path),
            sample_rate=settings.ws_sample_rate_hz,
            hotword_score=settings.hotword_score,
        )
        warmup_recognizer(recognizer, settings.ws_sample_rate_hz)
        misses = 0
        decoded: list[str] = []
        for doctor in names:
            spoken = doctor.replace("Dr.", "").strip()
            pcm = synth(f"see doctor {spoken}")
            hypo, _drain = decode_utterance(
                recognizer,
                pcm,
                settings.ws_sample_rate_hz,
            )
            decoded.append(hypo.text)
            if not _contains_name(hypo.text, doctor):
                misses += 1
    except (OSError, ValueError, RuntimeError, TtsError, ImportError) as exc:
        return blocked_row("asr.entity_wer.bias_off", f"entity_wer_failed:{type(exc).__name__}")
    rate = misses / len(names)
    return BenchRow(
        name="asr.entity_wer.bias_off",
        status="ok",
        version="zipformer2;piper;roster30",
        extra={
            "entity_error_rate": rate,
            "misses": misses,
            "n": len(names),
            "hotwords": 0,
            "transcripts": decoded,
        },
    )


def _contains_name(hypothesis: str, name: str) -> bool:
    hay = {token.strip(".,").lower() for token in hypothesis.split()}
    tokens = [token.strip(".,").lower() for token in name.replace("Dr.", " ").split() if token]
    return bool(tokens) and all(token in hay for token in tokens)
