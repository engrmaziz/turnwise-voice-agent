"""Recognize rendered scripts. CI uses a stub substitution; Zipformer is opt-in."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from nlp.hotwords import load_roster
from nlp.nlu_features import tokenize
from training.nlu.align_bio import bio_from_slots, project_bio
from training.nlu.generate import load_jsonl
from training.nlu.schema import AsrTrainRow, CallerScript

FORCED_SUB = ("Lang", "Lan")
TranscribeFn = Callable[[str], str]


def stub_asr(clean: str) -> str:
    """Return the clean text with one forced substitution so CI can align."""
    needle, repl = FORCED_SUB
    if needle in clean:
        return clean.replace(needle, repl, 1)
    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0]} uh {' '.join(parts[1:])}"
    return f"{clean} uh"


def recognize_scripts(
    scripts_path: Path,
    out_path: Path,
    *,
    transcribe: TranscribeFn | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[AsrTrainRow]:
    asr_fn = transcribe if transcribe is not None else stub_asr
    scripts = load_jsonl(scripts_path)
    rows: list[AsrTrainRow] = []
    total = len(scripts)
    for index, script in enumerate(scripts, start=1):
        rows.append(_row_from_script(script, asr_fn(script.text)))
        if progress is not None:
            progress(index, total)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")
    return rows


def zipformer_transcribe(*, with_hotwords: bool) -> TranscribeFn:
    """Piper-speak then Zipformer-decode. Missing weights are an error, not a stub."""
    from evals.bench.asr_compare import load_piper_synth, zipformer_unavailable_reason
    from models.asr_zipformer import decode_utterance, load_zipformer_recognizer, warmup_recognizer
    from server.config import Settings

    settings = Settings()
    blocked = zipformer_unavailable_reason(settings)
    if blocked is not None:
        raise RuntimeError(f"zipformer unavailable: {blocked}")
    synth = load_piper_synth(settings)
    if synth is None:
        raise RuntimeError("zipformer recognize needs Piper")
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
    hotwords: tuple[str, ...] = ()
    if with_hotwords:
        hotwords = load_roster(Path(settings.doctor_roster_path))

    def run(text: str) -> str:
        pcm = synth(text)
        hypo, _drain = decode_utterance(
            recognizer,
            pcm,
            settings.ws_sample_rate_hz,
            hotwords=hotwords,
        )
        return hypo.text

    return run


def _row_from_script(script: CallerScript, asr_text: str) -> AsrTrainRow:
    clean_tokens = tokenize(script.text)
    clean_tags = bio_from_slots(script.text, script.slots)
    asr_tokens = tokenize(asr_text)
    bio, align_low = project_bio(clean_tokens, clean_tags, asr_tokens)
    return AsrTrainRow(
        script_id=script.script_id,
        spoken_clean=script.text,
        asr_text=asr_text,
        intent=script.intent,
        bio_asr=bio,
        align_low=align_low,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scripts", type=Path, default=Path("training/nlu/fixture_scripts.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    parser.add_argument("--backend", choices=("stub", "zipformer"), default="stub")
    parser.add_argument(
        "--hotwords",
        action="store_true",
        help="Pass the doctor roster into Zipformer create_stream.",
    )
    args = parser.parse_args(argv)
    transcribe: TranscribeFn | None = None
    progress: Callable[[int, int], None] | None = None
    if args.backend == "zipformer":
        transcribe = zipformer_transcribe(with_hotwords=args.hotwords)

        def progress(index: int, total: int) -> None:
            if index == total or index % 25 == 0:
                print(f"asr_backend=zipformer {index}/{total}", flush=True)

    rows = recognize_scripts(args.scripts, args.out, transcribe=transcribe, progress=progress)
    if args.backend == "stub":
        print(f"asr_backend=stub rows={len(rows)} forced_sub={FORCED_SUB[0]}->{FORCED_SUB[1]}")
    else:
        print(f"asr_backend=zipformer rows={len(rows)} hotwords={int(args.hotwords)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
