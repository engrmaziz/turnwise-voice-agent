"""Entity WER with hotword bias on and off. Missing TTS or hotword API is not a number."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.asr_compare import SynthFn, load_piper_synth, zipformer_unavailable_reason
from evals.bench.harness import blocked_row
from evals.bench.schema import BenchRow
from models.asr_zipformer import decode_utterance, load_zipformer_recognizer, warmup_recognizer
from models.tts_pool import TtsError
from nlp.hotwords import load_roster
from server.config import Settings

# Plan T3.3.3 STARTING POINT 1.5; sweep these three and keep the lowest entity WER.
SCORE_SWEEP = (1.0, 1.5, 2.0)


def measure_entity_wer(settings: Settings, *, supports_hotwords: bool) -> list[BenchRow]:
    """Synthesize the roster through Piper. Blocked TTS is not text-only WER."""
    roster = load_roster(Path(settings.doctor_roster_path))
    if len(roster) < 15:
        raise RuntimeError("roster must have at least 15 invented names")
    names = list(roster) + list(roster)[:15]
    names = names[:30]
    blocked = zipformer_unavailable_reason(settings)
    if blocked is not None:
        off = blocked_row("asr.entity_wer.bias_off", blocked)
        on_reason = "unsupported" if not supports_hotwords else blocked
        return [off, blocked_row("asr.entity_wer.bias_on", on_reason)]
    synth = load_piper_synth(settings)
    if synth is None:
        off = blocked_row("asr.entity_wer.bias_off", "tts_blocked")
        on_reason = "unsupported" if not supports_hotwords else "tts_blocked"
        return [off, blocked_row("asr.entity_wer.bias_on", on_reason)]
    try:
        spoken_pcm = _synth_roster(synth, names)
    except (OSError, ValueError, RuntimeError, TtsError) as exc:
        return [
            blocked_row("asr.entity_wer.bias_off", f"entity_wer_failed:{type(exc).__name__}"),
            blocked_row("asr.entity_wer.bias_on", f"entity_wer_failed:{type(exc).__name__}"),
        ]
    off = _decode_row(
        settings,
        spoken_pcm,
        hotwords=(),
        score=settings.hotword_score,
        name="asr.entity_wer.bias_off",
    )
    if not supports_hotwords:
        return [off, blocked_row("asr.entity_wer.bias_on", "unsupported")]
    if off.status != "ok":
        return [off, blocked_row("asr.entity_wer.bias_on", off.reason or "bias_off_failed")]
    on, sweep = _sweep_bias_on(settings, spoken_pcm, roster)
    on.extra["score_sweep"] = sweep
    return [off, on]


def write_entity_json(rows: list[BenchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([row.model_dump() for row in rows], indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
    csv_path = path.with_suffix(".csv")
    lines = ["bias,entity_wer,status,hotwords,hotword_score"]
    for row in rows:
        bias = "on" if row.name.endswith("bias_on") else "off"
        rate = row.extra.get("entity_error_rate", "")
        hotwords = row.extra.get("hotwords", "")
        score = row.extra.get("hotword_score", "")
        lines.append(f"{bias},{rate},{row.status},{hotwords},{score}")
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _synth_roster(synth: SynthFn, names: list[str]) -> list[tuple[str, bytes]]:
    spoken_pcm: list[tuple[str, bytes]] = []
    for doctor in names:
        spoken = doctor.replace("Dr.", "").strip()
        spoken_pcm.append((doctor, synth(f"see doctor {spoken}")))
    return spoken_pcm


def _sweep_bias_on(
    settings: Settings,
    spoken_pcm: list[tuple[str, bytes]],
    roster: tuple[str, ...],
) -> tuple[BenchRow, list[dict[str, float | int]]]:
    sweep: list[dict[str, float | int]] = []
    rows: list[BenchRow] = []
    for score in SCORE_SWEEP:
        row = _decode_row(
            settings,
            spoken_pcm,
            hotwords=tuple(roster),
            score=score,
            name="asr.entity_wer.bias_on",
        )
        rows.append(row)
        extra = row.extra
        raw_rate = extra.get("entity_error_rate", 1.0)
        raw_misses = extra.get("misses", len(spoken_pcm))
        rate = float(raw_rate) if isinstance(raw_rate, int | float) else 1.0
        misses = int(raw_misses) if isinstance(raw_misses, int | float) else len(spoken_pcm)
        sweep.append({"hotword_score": score, "entity_error_rate": rate, "misses": misses})
    chosen = _pick_score(rows)
    return chosen, sweep


def _pick_score(rows: list[BenchRow]) -> BenchRow:
    ok_rows = [row for row in rows if row.status == "ok"]
    if not ok_rows:
        return rows[-1]
    def rate_of(row: BenchRow) -> float:
        raw = row.extra.get("entity_error_rate", 1.0)
        return float(raw) if isinstance(raw, int | float) else 1.0

    best_rate = min(rate_of(row) for row in ok_rows)
    tied = [row for row in ok_rows if rate_of(row) == best_rate]
    for row in tied:
        if row.extra.get("hotword_score") == 1.5:
            return row
    return tied[0]


def _decode_row(
    settings: Settings,
    spoken_pcm: list[tuple[str, bytes]],
    *,
    hotwords: tuple[str, ...],
    score: float,
    name: str,
) -> BenchRow:
    try:
        recognizer = load_zipformer_recognizer(
            encoder=Path(settings.asr_zipformer_encoder_path),
            decoder=Path(settings.asr_zipformer_decoder_path),
            joiner=Path(settings.asr_zipformer_joiner_path),
            tokens=Path(settings.asr_zipformer_tokens_path),
            sample_rate=settings.ws_sample_rate_hz,
            hotword_score=score,
            bpe_vocab=Path(settings.asr_zipformer_bpe_vocab_path),
            bpe_model=Path(settings.asr_zipformer_bpe_model_path),
        )
        warmup_recognizer(recognizer, settings.ws_sample_rate_hz)
        misses = 0
        decoded: list[str] = []
        for doctor, pcm in spoken_pcm:
            hypo, _drain = decode_utterance(
                recognizer,
                pcm,
                settings.ws_sample_rate_hz,
                hotwords=hotwords,
            )
            decoded.append(hypo.text)
            if not _contains_name(hypo.text, doctor):
                misses += 1
    except (OSError, ValueError, RuntimeError, TtsError, ImportError) as exc:
        return blocked_row(name, f"entity_wer_failed:{type(exc).__name__}")
    rate = misses / len(spoken_pcm)
    return BenchRow(
        name=name,
        status="ok",
        version="zipformer2;beam;bpe;piper;roster30",
        extra={
            "entity_error_rate": rate,
            "misses": misses,
            "n": len(spoken_pcm),
            "hotwords": len(hotwords),
            "hotword_score": score,
            "transcripts": decoded,
        },
    )


def _contains_name(hypothesis: str, name: str) -> bool:
    hay = {token.strip(".,").lower() for token in hypothesis.split()}
    tokens = [token.strip(".,").lower() for token in name.replace("Dr.", " ").split() if token]
    return bool(tokens) and all(token in hay for token in tokens)


def main() -> int:
    from server.config import get_settings

    settings = get_settings()
    rows = measure_entity_wer(settings, supports_hotwords=True)
    out = Path("docs/results/phase3_entity_wer.json")
    write_entity_json(rows, out)
    for row in rows:
        extra = {key: value for key, value in row.extra.items() if key != "transcripts"}
        print(json.dumps({"name": row.name, "status": row.status, "extra": extra}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
