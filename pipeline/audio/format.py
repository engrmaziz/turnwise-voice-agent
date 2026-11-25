"""The only resampler. Downstream stages receive 16 kHz mono PCM16."""

from __future__ import annotations

import struct


def resample_mono_pcm16(pcm: bytes, src_hz: int, dst_hz: int) -> bytes:
    """Linear interpolation of little-endian int16 mono. Identity when rates match.

    Odd byte length means the buffer is not mono PCM16. Stereo is rejected
    here rather than mixed down in a later stage.
    """
    if src_hz < 1 or dst_hz < 1:
        raise ValueError("sample rates must be >= 1")
    if len(pcm) % 2 != 0:
        raise ValueError("pcm16 byte length must be even")
    if src_hz == dst_hz:
        return pcm
    n_src = len(pcm) // 2
    if n_src == 0:
        return b""
    src = struct.unpack(f"<{n_src}h", pcm)
    n_dst = max(1, round(n_src * dst_hz / src_hz))
    ratio = n_src / n_dst
    out = [0] * n_dst
    last = n_src - 1
    for i in range(n_dst):
        pos = i * ratio
        left = int(pos)
        if left >= last:
            out[i] = src[last]
            continue
        frac = pos - left
        sample = src[left] * (1.0 - frac) + src[left + 1] * frac
        if sample >= 32767.0:
            out[i] = 32767
        elif sample <= -32768.0:
            out[i] = -32768
        else:
            out[i] = round(sample)
    return struct.pack(f"<{n_dst}h", *out)
