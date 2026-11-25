"""10 s of 16 kHz audio for the ASR bench. Speech only if a local synthesizer runs."""

from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

from evals.bench.asr import FIXTURE_LICENSE, FIXTURE_TEXT

RATE_HZ = 16000
DURATION_S = 10.0


def write_tone_wav(path: Path, *, seconds: float = DURATION_S, rate: int = RATE_HZ) -> None:
    """440 Hz sine at 0.1 amplitude. Not speech. ASR must not treat this as a voice fixture."""
    samples = int(seconds * rate)
    frames = bytearray()
    for i in range(samples):
        value = int(32767 * 0.1 * math.sin(2.0 * math.pi * 440.0 * i / rate))
        frames.extend(struct.pack("<h", value))
    _write_wav(path, bytes(frames), rate)


def try_sapi_wav(path: Path, text: str = FIXTURE_TEXT) -> bool:
    """Windows SAPI. Returns False when PowerShell or the synthesizer is missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wav = str(path.resolve())
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav}'); "
        f"$s.Speak('{_ps_escape(text)}'); "
        "$s.Dispose();"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and path.is_file() and path.stat().st_size > 44


def prepare_fixture(directory: Path) -> tuple[Path, str, Path | None]:
    """Return (tone_or_speech_path, audio_kind, speech_path_or_none)."""
    directory.mkdir(parents=True, exist_ok=True)
    speech = directory / "north_wind.wav"
    if try_sapi_wav(speech):
        return speech, "windows_sapi", speech
    tone = directory / "tone_placeholder.wav"
    write_tone_wav(tone)
    return tone, "tone_placeholder_not_speech", None


def fixture_license() -> str:
    return FIXTURE_LICENSE


def fixture_text() -> str:
    return FIXTURE_TEXT


def _write_wav(path: Path, pcm: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)


def _ps_escape(text: str) -> str:
    return text.replace("'", "''")
