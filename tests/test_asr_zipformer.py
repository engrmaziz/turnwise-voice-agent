"""Zipformer pool: missing weights raise; real decode is skipped in CI."""

import importlib.util
import wave
from pathlib import Path

import pytest

from models.asr_pool import AsrPool
from models.asr_zipformer import join_hotword_phrases, write_bpe_vocab
from pipeline.audio.format import resample_mono_pcm16
from tests.conftest import Harness

_ENCODER = Path("models/weights/zipformer/encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx")
_WAV = Path("docs/results/bench/fixtures/north_wind.wav")


def _zipformer_ready() -> bool:
    return importlib.util.find_spec("sherpa_onnx") is not None and _ENCODER.is_file()


def test_write_bpe_vocab_from_tokens(tmp_path: Path) -> None:
    tokens = tmp_path / "tokens.txt"
    tokens.write_text("<blk> 0\n<unk> 1\n▁THE 2\n", encoding="utf-8")
    dest = tmp_path / "bpe.vocab"
    write_bpe_vocab(tokens, dest)
    assert dest.read_text(encoding="utf-8") == "<unk>\t5.0\n▁THE\t4.0\n"


def test_join_hotword_phrases_uppercases_roster() -> None:
    assert join_hotword_phrases(("Dr. Khan", "Dr. Avery Lang")) == "KHAN/AVERY LANG"


def test_zipformer_missing_encoder_raises(tmp_path: Path, harness: Harness) -> None:
    configured = harness.settings.model_copy(
        update={
            "asr_backend": "zipformer",
            "asr_zipformer_encoder_path": str(tmp_path / "missing.onnx"),
        }
    )
    with pytest.raises(FileNotFoundError, match="zipformer weight missing"):
        AsrPool.zipformer(configured, harness.metrics)


@pytest.mark.skipif(
    not _zipformer_ready() or not _WAV.is_file(),
    reason="zipformer extra or wav missing",
)
async def test_zipformer_decodes_north_wind(harness: Harness) -> None:
    configured = harness.settings.model_copy(update={"asr_finish_timeout_ms": 5000})
    pool = AsrPool.zipformer(configured, harness.metrics)
    stream = pool.start_stream(
        harness.session.session_id,
        harness.session.generation,
        live=lambda: harness.session.generation,
        speaking=lambda: True,
    )
    with wave.open(str(_WAV), "rb") as wav:
        raw = wav.readframes(wav.getnframes())
        src_hz = wav.getframerate()
    pcm = resample_mono_pcm16(raw, src_hz, harness.settings.ws_sample_rate_hz)
    frame = harness.settings.ws_sample_rate_hz * 2 // 50
    for offset in range(0, len(pcm), frame):
        await stream.push(pcm[offset : offset + frame])
    result = await stream.finish()
    pool.close()
    assert result is not None
    assert result.is_final
    spoken = result.text.upper()
    assert "NORTH" in spoken
    assert "WIND" in spoken
