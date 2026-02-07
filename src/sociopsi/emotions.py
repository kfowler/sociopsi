"""Emergent emotions from modulator + drive configurations.

Emotions in PSI theory are not explicitly programmed but emerge from
combinations of modulator values and drive states. This module detects
emotional states from those configurations and tracks transitions.

Reference: Dorner PSI theory Ch. 7 (Emotions as modulator configurations).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sociopsi.drives import DriveSystem
    from sociopsi.modulators import ModulatorLayer


@dataclass
class EmotionState:
    """A detected emotional state with intensity and valence."""

    name: str
    intensity: float  # 0.0 to 1.0
    valence: float  # -1.0 (negative) to 1.0 (positive)

    def __repr__(self) -> str:
        sign = "+" if self.valence >= 0 else ""
        return f"EmotionState({self.name}, intensity={self.intensity:.2f}, valence={sign}{self.valence:.2f})"


# Each emotion rule: (name, valence, detector function)
# Detector returns intensity (0.0-1.0) given modulators and drives


def _detect_anger(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """High arousal + low resolution + competence frustration."""
    arousal = mods.arousal_level
    low_res = 1.0 - mods.resolution
    comp_frust = ds.drives["competence"].demand
    raw = arousal * 0.4 + low_res * 0.3 + comp_frust * 0.3
    return max(0.0, min(1.0, raw * 1.5 - 0.3))


def _detect_fear(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """High arousal + certainty frustration + integrity threat."""
    arousal = mods.arousal_level
    cert_frust = ds.drives["certainty"].demand
    integ_threat = ds.drives["integrity"].demand
    raw = arousal * 0.3 + cert_frust * 0.35 + integ_threat * 0.35
    return max(0.0, min(1.0, raw * 1.5 - 0.3))


def _detect_joy(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """Satisfaction across drives + high resolution."""
    avg_sat = 1.0 - sum(d.demand for d in ds.drives.values()) / len(ds.drives)
    resolution = mods.resolution
    raw = avg_sat * 0.6 + resolution * 0.4
    return max(0.0, min(1.0, raw * 1.5 - 0.3))


def _detect_sadness(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """Low arousal + affiliation frustration."""
    low_arousal = 1.0 - mods.arousal_level
    affil_frust = ds.drives["affiliation"].demand
    raw = low_arousal * 0.4 + affil_frust * 0.6
    return max(0.0, min(1.0, raw * 1.5 - 0.3))


def _detect_curiosity(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """High arousal + moderate resolution + certainty frustration."""
    arousal = mods.arousal_level
    # Moderate resolution: peaks at 0.5, drops toward 0 and 1
    res_moderate = 1.0 - abs(mods.resolution - 0.5) * 2.0
    cert_frust = ds.drives["certainty"].demand
    curio_demand = ds.drives["curiosity"].demand
    raw = arousal * 0.2 + res_moderate * 0.2 + cert_frust * 0.3 + curio_demand * 0.3
    return max(0.0, min(1.0, raw * 1.5 - 0.2))


def _detect_boredom(mods: ModulatorLayer, ds: DriveSystem) -> float:
    """Low arousal + low curiosity satisfaction."""
    low_arousal = 1.0 - mods.arousal_level
    curio_demand = ds.drives["curiosity"].demand
    low_res = 1.0 - mods.resolution
    raw = low_arousal * 0.4 + curio_demand * 0.4 + low_res * 0.2
    return max(0.0, min(1.0, raw * 1.5 - 0.4))


# Emotion rules: (name, valence, detector)
EMOTION_RULES: list[tuple[str, float, Any]] = [
    ("anger", -0.8, _detect_anger),
    ("fear", -0.9, _detect_fear),
    ("joy", 0.9, _detect_joy),
    ("sadness", -0.6, _detect_sadness),
    ("curiosity", 0.5, _detect_curiosity),
    ("boredom", -0.3, _detect_boredom),
]


@dataclass
class EmotionSystem:
    """Detects and tracks emergent emotions from modulator/drive configurations.

    Emotions are computed each cycle from the current modulator and drive
    states. The dominant emotion (highest intensity above threshold) becomes
    the current emotional state. Transitions are logged for memory integration.
    """

    threshold: float = 0.15
    _current: EmotionState | None = field(default=None, repr=False)
    _previous: EmotionState | None = field(default=None, repr=False)
    _all_emotions: list[EmotionState] = field(default_factory=list, repr=False)
    _transition_log: list[tuple[str | None, str | None, float]] = field(
        default_factory=list, repr=False
    )

    @property
    def current(self) -> EmotionState | None:
        """The current dominant emotion, or None if below threshold."""
        return self._current

    @property
    def previous(self) -> EmotionState | None:
        """The previous dominant emotion before the last transition."""
        return self._previous

    @property
    def all_emotions(self) -> list[EmotionState]:
        """All detected emotions from the last update, sorted by intensity."""
        return list(self._all_emotions)

    def update(self, modulators: ModulatorLayer, drive_system: DriveSystem) -> EmotionState | None:
        """Detect emotions from current modulator + drive configuration.

        Args:
            modulators: Current modulator layer state.
            drive_system: Current drive system state.

        Returns:
            The dominant emotion if above threshold, else None.
        """
        detected: list[EmotionState] = []
        for name, valence, detector in EMOTION_RULES:
            intensity = detector(modulators, drive_system)
            if intensity > 0:
                detected.append(EmotionState(name=name, intensity=intensity, valence=valence))

        detected.sort(key=lambda e: e.intensity, reverse=True)
        self._all_emotions = detected

        # Determine dominant emotion
        dominant = detected[0] if detected and detected[0].intensity >= self.threshold else None

        # Track transitions
        old_name = self._current.name if self._current else None
        new_name = dominant.name if dominant else None
        if old_name != new_name:
            self._previous = self._current
            self._transition_log.append(
                (old_name, new_name, dominant.intensity if dominant else 0.0)
            )
            # Keep log bounded
            if len(self._transition_log) > 50:
                self._transition_log = self._transition_log[-50:]

        self._current = dominant
        return dominant

    def get_valence(self) -> float:
        """Get the current emotional valence for memory integration.

        Returns:
            Valence from -1.0 to 1.0, or 0.0 if no emotion detected.
        """
        if self._current:
            return self._current.valence * self._current.intensity
        return 0.0

    def had_transition(self) -> bool:
        """Check if the last update caused an emotion transition."""
        if not self._transition_log:
            return False
        old, new, _ = self._transition_log[-1]
        return old != new

    def get_last_transition(self) -> tuple[str | None, str | None] | None:
        """Get the most recent emotion transition (old_name, new_name)."""
        if not self._transition_log:
            return None
        old, new, _ = self._transition_log[-1]
        return (old, new)

    def format_for_perception(self) -> str:
        """Format emotional state for inclusion in perception prompt."""
        if not self._all_emotions:
            return ""

        lines = ["[EMOTIONS]"]
        for emotion in self._all_emotions:
            if emotion.intensity >= self.threshold:
                bar = _bar(emotion.intensity)
                sign = "+" if emotion.valence >= 0 else ""
                lines.append(
                    f"  {emotion.name:12} {bar} {emotion.intensity:.2f} "
                    f"(valence: {sign}{emotion.valence:.1f})"
                )

        if self._current:
            lines.append(f"  dominant: {self._current.name}")

        if self.had_transition():
            old, new = self.get_last_transition()  # type: ignore[misc]
            old_str = old or "neutral"
            new_str = new or "neutral"
            lines.append(f"  transition: {old_str} -> {new_str}")

        return "\n".join(lines)

    def get_dialogue_context(self) -> dict[str, Any]:
        """Get emotion context for the dialogue system."""
        ctx: dict[str, Any] = {
            "emotion": self._current.name if self._current else None,
            "emotion_intensity": self._current.intensity if self._current else 0.0,
            "emotion_valence": self.get_valence(),
        }
        if self._all_emotions:
            ctx["emotions"] = {
                e.name: e.intensity for e in self._all_emotions if e.intensity >= self.threshold
            }
        if self.had_transition():
            old, new = self.get_last_transition()  # type: ignore[misc]
            ctx["emotion_transition"] = {"from": old, "to": new}
        return ctx

    def get_state(self) -> dict[str, Any]:
        """Get emotion state for logging."""
        return {
            "current": self._current.name if self._current else None,
            "intensity": self._current.intensity if self._current else 0.0,
            "valence": self.get_valence(),
            "all": {e.name: e.intensity for e in self._all_emotions},
            "transition_count": len(self._transition_log),
        }


def _bar(value: float) -> str:
    """Visual bar for a 0-1 value."""
    filled = int(value * 10)
    return "\u2588" * filled + "\u2591" * (10 - filled)
