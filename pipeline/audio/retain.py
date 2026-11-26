"""Optional utterance WAV retention. Default off. Path comes from settings."""

from __future__ import annotations

import time
import wave
from pathlib import Path

from server.config import Settings

_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2
_CHANNELS = 1


def retain_pcm(pcm: bytes, *, settings: Settings, now_s: float | None = None) -> Path | None:
    """Write PCM16 only when audio_retain is true. Never uses an implicit /tmp."""
    if not settings.audio_retain:
        return None
    if not pcm:
        raise ValueError("retain pcm must be non-empty")
    root = Path(settings.audio_retain_dir)
    root.mkdir(parents=True, exist_ok=True)
    expire_old(root, settings.audio_retain_s, now_s=now_s)
    stamp = int(now_s if now_s is not None else time.time())
    path = root / f"utt-{stamp}.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(_CHANNELS)
        handle.setsampwidth(_SAMPLE_WIDTH)
        handle.setframerate(_SAMPLE_RATE)
        handle.writeframes(pcm)
    return path


def expire_old(root: Path, retain_s: int, *, now_s: float | None = None) -> int:
    """Delete wavs older than retain_s. retain_s 0 expires everything."""
    if not root.is_dir():
        return 0
    now = now_s if now_s is not None else time.time()
    removed = 0
    for path in root.glob("*.wav"):
        age = now - path.stat().st_mtime
        if age >= retain_s:
            path.unlink()
            removed += 1
    return removed
