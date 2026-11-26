"""Two-turn frustration latch. Offering a human is not a handoff."""

from __future__ import annotations

from dataclasses import dataclass

from server.config import Settings


@dataclass(slots=True)
class FrustrationLatch:
    """Count consecutive over-threshold turns. A single spike does not stick."""

    streak: int = 0
    offer_human: bool = False
    _offered_say: bool = False

    def note(self, score: float, settings: Settings) -> bool:
        """Update the streak. Below-threshold resets the count, not a prior latch."""
        if score >= settings.frustration_threshold:
            self.streak += 1
        else:
            self.streak = 0
        if self.streak >= settings.frustration_turns:
            self.offer_human = True
        return self.offer_human

    def take_offer_say(self) -> bool:
        """True once, the first time the latch fires, so the offer is spoken once."""
        if self.offer_human and not self._offered_say:
            self._offered_say = True
            return True
        return False
