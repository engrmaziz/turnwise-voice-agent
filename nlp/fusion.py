"""Late-fusion frustration score. Dialogue terms run when audio is missing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from server.config import Settings


class EmotionProbs(BaseModel):
    """Three-class utterance scores. A 7-class dataset never reaches the FSM."""

    model_config = ConfigDict(frozen=True)

    calm: float = Field(ge=0.0)
    frustrated: float = Field(ge=0.0)
    distressed: float = Field(ge=0.0)
    generation: int = Field(ge=0)


def fuse(
    audio: EmotionProbs | None,
    text_score: float | None,
    repairs: int,
    repeated_no: int,
    barged: bool,
    settings: Settings,
) -> float:
    """Weighted sum in ``[0, 1]``. Missing audio is a zero first term, not a skip.

    Starting weights cannot reach ``frustration_threshold`` (0.65) without audio:
    the dialogue terms max out at 0.6. Tests lock the arithmetic to 1e-6 rather
    than fudge the weights so a no-audio case looks like it crosses the gate.
    """
    audio_term = 0.0 if audio is None else min(1.0, max(0.0, audio.distressed + audio.frustrated))
    clipped = 0.5 if text_score is None else min(1.0, max(0.0, text_score))
    repair_term = min(1.0, max(0, repairs) / 3.0)
    no_term = min(1.0, max(0, repeated_no) / 2.0)
    barge_term = 1.0 if barged else 0.0
    score = (
        settings.fuse_w_audio * audio_term
        + settings.fuse_w_text * (1.0 - clipped)
        + settings.fuse_w_repair * repair_term
        + settings.fuse_w_no * no_term
        + settings.fuse_w_barge * barge_term
    )
    return min(1.0, max(0.0, score))
