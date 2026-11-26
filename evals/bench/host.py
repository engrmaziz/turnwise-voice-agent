"""Host identity for the JSON log. A second machine needs a second JSON file."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from evals.bench.schema import HostInfo

_NVIDIA_TIMEOUT_S = 5.0


def collect_host(*, nvidia_smi: str | None = None) -> HostInfo:
    smi_status, smi_text = probe_nvidia(nvidia_smi)
    return HostInfo(
        platform=platform.platform(),
        python=sys.version.split()[0],
        cpu_count=os.cpu_count() or 0,
        ram_gb=_ram_gb(),
        nvidia_smi=smi_text,
        nvidia_status=smi_status,
    )


def probe_nvidia(
    binary: str | None = None,
) -> tuple[Literal["present", "not_present"], str | None]:
    """``not_present`` when the binary is missing, times out, or exits non-zero."""
    resolved = binary if binary else shutil.which("nvidia-smi")
    if resolved is None:
        return "not_present", None
    try:
        proc = subprocess.run(
            [
                resolved,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=_NVIDIA_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "not_present", None
    if proc.returncode != 0:
        return "not_present", None
    detail = proc.stdout.strip()
    if not detail:
        return "not_present", None
    return "present", detail


def _ram_gb() -> float | None:
    if sys.platform == "win32":
        return _ram_gb_windows()
    meminfo = _read_meminfo_kb()
    if meminfo is None:
        return None
    return round(meminfo / (1024.0 * 1024.0), 2)


def _ram_gb_windows() -> float | None:
    # ctypes.windll exists only on Windows. The check belongs in this function
    # so Linux mypy (GitHub Actions) does not see an undefined attribute.
    if sys.platform != "win32":
        return None
    import ctypes

    class _MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) == 0:
        return None
    return round(float(status.ullTotalPhys) / (1024.0**3), 2)


def _read_meminfo_kb() -> float | None:
    path = Path("/proc/meminfo")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            return float(parts[1])
    return None
