"""Insert one T5.5.1 repair marker when the scenario asks for disfluency."""

from __future__ import annotations

from server.config import Settings

_MARKERS = ("no", "sorry", "i mean", "actually")


def inject_disfluency(text: str, *, enabled: bool, settings: Settings | None = None) -> str:
    if not enabled:
        return text
    marker = _MARKERS[0]
    if settings is not None:
        parts = tuple(item.strip() for item in settings.repair_markers.split(",") if item.strip())
        if parts:
            marker = parts[0]
    stripped = text.strip()
    if not stripped:
        return marker
    return f"{stripped}, {marker} {stripped}"
