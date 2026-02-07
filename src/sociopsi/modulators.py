"""MicroPsi2 modulator layer - shapes cognitive processing quality.

Implements five modulators from Bach's Psi theory that alter HOW the agent
thinks, not just WHAT it attends to. Drives determine motivation; modulators
determine the quality and character of processing.

Reference: Bach 2012, MicroPsi2 paper, Section 3 (Modulators).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from sociopsi.drives import DriveSystem


class ModulatorState(TypedDict):
    """Snapshot of all modulator values for logging."""

    arousal_level: float
    resolution: float
    selection_threshold: float
    securing_rate: float
    goal_valuation: float


@dataclass
class ModulatorLayer:
    """Computes five modulators from drive states each cycle.

    Modulators shape cognitive processing:
    - arousal_level: Energetic activation. High = fast/scattered, low = slow/focused.
    - resolution: Commitment to current goals. High = narrow focus, low = diffuse.
    - selection_threshold: Persistence before abandoning a goal. High = stubborn, low = flighty.
    - securing_rate: Speed of memory consolidation. High = writes often, low = forgets.
    - goal_valuation: Reward/punishment weighting. High = reward-seeking, low = punishment-avoiding.
    """

    arousal_level: float = 0.5
    resolution: float = 0.5
    selection_threshold: float = 0.5
    securing_rate: float = 0.5
    goal_valuation: float = 0.5

    # Smoothing factor: how much new values blend with old (0 = no change, 1 = instant)
    _smoothing: float = field(default=0.3, repr=False)

    def update(self, drive_system: DriveSystem) -> None:
        """Recompute modulators from current drive states.

        Each modulator is derived from a combination of drive demands and
        urgencies, then smoothed to avoid jitter.
        """
        drives = drive_system.drives
        s = self._smoothing

        # --- Arousal Level ---
        # High arousal drive demand + high curiosity + recent failures = high activation
        # Low arousal demand + satisfaction = calm processing
        raw_arousal = (
            drives["arousal"].demand * 0.5
            + drives["curiosity"].demand * 0.2
            + drives["energy"].demand * 0.15
            + drives["affiliation"].demand * 0.15
        )
        self.arousal_level = _smooth(self.arousal_level, raw_arousal, s)

        # --- Resolution ---
        # High competence satisfaction + high certainty = high resolution (focused)
        # Frustration (high competence demand) + uncertainty = low resolution (scattered)
        competence_sat = 1.0 - drives["competence"].demand
        certainty_sat = 1.0 - drives["certainty"].demand
        raw_resolution = (
            competence_sat * 0.4
            + certainty_sat * 0.3
            + (1.0 - drives["arousal"].demand) * 0.3
        )
        self.resolution = _smooth(self.resolution, raw_resolution, s)

        # --- Selection Threshold ---
        # High integrity + low arousal = persistent (high threshold)
        # High arousal + low competence satisfaction = give up quickly (low threshold)
        raw_threshold = (
            (1.0 - drives["integrity"].demand) * 0.3
            + (1.0 - drives["arousal"].demand) * 0.3
            + competence_sat * 0.2
            + certainty_sat * 0.2
        )
        self.selection_threshold = _smooth(self.selection_threshold, raw_threshold, s)

        # --- Securing Rate ---
        # High certainty demand = write memories more (trying to ground)
        # High arousal = too activated to consolidate
        # High individuation demand = deep integration
        raw_securing = (
            drives["certainty"].demand * 0.3
            + drives["individuation"].demand * 0.3
            + (1.0 - drives["arousal"].demand) * 0.2
            + competence_sat * 0.2
        )
        self.securing_rate = _smooth(self.securing_rate, raw_securing, s)

        # --- Goal Valuation ---
        # High energy + low integrity concern = reward-seeking (positive valence)
        # Low energy + high integrity concern = punishment-avoiding (negative valence)
        # 0.5 = neutral, >0.5 = reward-oriented, <0.5 = punishment-oriented
        energy_sat = 1.0 - drives["energy"].demand
        integrity_ok = 1.0 - drives["integrity"].demand
        raw_valuation = (
            energy_sat * 0.3
            + integrity_ok * 0.3
            + competence_sat * 0.2
            + (1.0 - drives["recognition"].demand) * 0.2
        )
        self.goal_valuation = _smooth(self.goal_valuation, raw_valuation, s)

    def get_temperature(self) -> float:
        """Map modulator state to LLM temperature.

        High arousal + low resolution = high temperature (creative, scattered).
        Low arousal + high resolution = low temperature (focused, deterministic).

        Returns:
            Temperature in [0.2, 1.2] range.
        """
        # Arousal pushes temperature up, resolution pulls it down
        raw = self.arousal_level * 0.6 + (1.0 - self.resolution) * 0.4
        return 0.2 + raw * 1.0  # Maps [0,1] -> [0.2, 1.2]

    def get_token_budget_factor(self) -> float:
        """Map modulator state to token budget scaling factor.

        High arousal + low resolution = shorter responses (scattered, terse).
        Low arousal + high resolution = longer responses (detailed, thorough).

        Returns:
            Factor in [0.4, 1.5] range to multiply base token limit.
        """
        # Resolution drives thoroughness, inverse arousal allows space
        raw = self.resolution * 0.6 + (1.0 - self.arousal_level) * 0.4
        return 0.4 + raw * 1.1  # Maps [0,1] -> [0.4, 1.5]

    def get_prompt_tone(self) -> str:
        """Generate a tone directive string for system prompt injection.

        Returns a short instruction that modulates the LLM's response style
        based on current modulator state.
        """
        parts: list[str] = []

        # Arousal -> energy of response
        if self.arousal_level > 0.7:
            parts.append("Respond with urgency and intensity.")
        elif self.arousal_level < 0.3:
            parts.append("Respond calmly and deliberately.")

        # Resolution -> focus
        if self.resolution > 0.7:
            parts.append("Stay narrowly focused on the most important concern.")
        elif self.resolution < 0.3:
            parts.append("Consider multiple angles loosely.")

        # Goal valuation -> orientation
        if self.goal_valuation > 0.7:
            parts.append("Emphasize opportunities and rewards.")
        elif self.goal_valuation < 0.3:
            parts.append("Watch for threats and risks.")

        # Selection threshold -> persistence attitude
        if self.selection_threshold > 0.7:
            parts.append("Persist with current approach.")
        elif self.selection_threshold < 0.3:
            parts.append("Be ready to switch strategies quickly.")

        if not parts:
            return ""
        return " ".join(parts)

    def get_memory_write_probability(self) -> float:
        """Map securing_rate to probability of writing to memory this cycle.

        Returns:
            Probability in [0.1, 0.9] range.
        """
        return 0.1 + self.securing_rate * 0.8

    def get_drive_satisfaction_multiplier(self) -> float:
        """Map goal_valuation to drive satisfaction multiplier.

        High goal valuation = amplify positive satisfaction signals.
        Low goal valuation = dampen them (more sensitive to punishment).

        Returns:
            Multiplier in [0.5, 1.5] range.
        """
        return 0.5 + self.goal_valuation * 1.0

    def format_for_perception(self) -> str:
        """Format modulator state for inclusion in perception prompt."""
        lines = ["[MODULATORS]"]
        for name, value, desc in [
            ("arousal_level", self.arousal_level, self._arousal_desc()),
            ("resolution", self.resolution, self._resolution_desc()),
            ("sel_threshold", self.selection_threshold, self._threshold_desc()),
            ("securing_rate", self.securing_rate, self._securing_desc()),
            ("goal_valuation", self.goal_valuation, self._valuation_desc()),
        ]:
            bar = _bar(value)
            lines.append(f"  {name:14} {bar} {value:.2f} {desc}")
        return "\n".join(lines)

    def get_state(self) -> ModulatorState:
        """Get modulator state for logging."""
        return ModulatorState(
            arousal_level=self.arousal_level,
            resolution=self.resolution,
            selection_threshold=self.selection_threshold,
            securing_rate=self.securing_rate,
            goal_valuation=self.goal_valuation,
        )

    def get_dialogue_context(self) -> dict[str, Any]:
        """Get modulator context for the dialogue system.

        Returns dict with keys archetype voices can use to modulate their tone.
        """
        return {
            "arousal_level": self.arousal_level,
            "resolution": self.resolution,
            "selection_threshold": self.selection_threshold,
            "securing_rate": self.securing_rate,
            "goal_valuation": self.goal_valuation,
            "tone": self.get_prompt_tone(),
            "temperature": self.get_temperature(),
        }

    # --- Private description helpers ---

    def _arousal_desc(self) -> str:
        if self.arousal_level > 0.7:
            return "activated"
        elif self.arousal_level < 0.3:
            return "calm"
        return "moderate"

    def _resolution_desc(self) -> str:
        if self.resolution > 0.7:
            return "focused"
        elif self.resolution < 0.3:
            return "scattered"
        return "balanced"

    def _threshold_desc(self) -> str:
        if self.selection_threshold > 0.7:
            return "persistent"
        elif self.selection_threshold < 0.3:
            return "flighty"
        return "flexible"

    def _securing_desc(self) -> str:
        if self.securing_rate > 0.7:
            return "consolidating"
        elif self.securing_rate < 0.3:
            return "transient"
        return "steady"

    def _valuation_desc(self) -> str:
        if self.goal_valuation > 0.7:
            return "reward-seeking"
        elif self.goal_valuation < 0.3:
            return "threat-avoiding"
        return "balanced"


def _smooth(old: float, new: float, factor: float) -> float:
    """Exponential moving average smoothing."""
    return _clamp(old + (new - old) * factor)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, v))


def _bar(value: float) -> str:
    """Visual bar for a 0-1 value."""
    filled = int(value * 10)
    return "\u2588" * filled + "\u2591" * (10 - filled)
