"""audio_retain false writes nothing. True expires files after audio_retain_s."""

import os
import time
from pathlib import Path

from pipeline.audio.retain import retain_pcm
from server.config import Settings


def test_retain_default_writes_nothing(tmp_path: Path) -> None:
    settings = Settings(audio_retain=False, audio_retain_dir=str(tmp_path / "retain"))
    pcm = b"\x00\x01" * 160
    assert retain_pcm(pcm, settings=settings) is None
    assert list((tmp_path / "retain").glob("*.wav")) == []


def test_retain_true_expires_after_one_second(tmp_path: Path) -> None:
    root = tmp_path / "retain"
    settings = Settings(
        audio_retain=True,
        audio_retain_s=1,
        audio_retain_dir=str(root),
        otel_enabled=False,
    )
    pcm = b"\x00\x01" * 160
    first = retain_pcm(pcm, settings=settings, now_s=1_000.0)
    assert first is not None
    assert first.is_file()
    time.sleep(0.05)
    first.touch()
    old = time.time() - 2
    os.utime(first, (old, old))
    second = retain_pcm(pcm, settings=settings, now_s=time.time())
    assert second is not None
    assert not first.exists()
    assert second.is_file()
