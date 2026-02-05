"""Archetypal modulation based on acoustic environment."""

from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.archetypes.base import Archetype


class ArchetypalModulator:
    """Modulates archetype activation based on acoustic environment."""

    def __init__(self, event_bus: EventBus, archetypes: dict[str, Archetype]) -> None:
        """Initialize archetypal modulator.

        Args:
            event_bus: Event bus for subscribing to ambient sound
            archetypes: Dict of archetype name to archetype instance
        """
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.base_weights = {name: 1.0 for name in archetypes}
        self.current_weights = self.base_weights.copy()

        event_bus.subscribe("perception.audio.ambient", self.on_ambient_sound)

    def on_ambient_sound(self, data: dict[str, Any]) -> None:
        """Adjust archetype weights based on acoustic environment.

        Args:
            data: Ambient sound event data
        """
        sound_type = data["type"]
        volume = data["volume"]

        # Reset to base
        new_weights = self.base_weights.copy()

        if sound_type == "silence":
            # Quiet contemplation - Self more active
            new_weights["self"] = 1.5
            new_weights["anima"] = 1.2
            new_weights["persona"] = 0.8
            new_weights["shadow"] = 0.7

        elif sound_type == "speech":
            # Social environment - Anima and Persona more active
            new_weights["anima"] = 1.4
            new_weights["persona"] = 1.3
            new_weights["self"] = 0.9
            new_weights["shadow"] = 0.8

        elif sound_type == "noise" and volume > 0.7:
            # Loud/chaotic - Shadow more active (survival mode)
            new_weights["shadow"] = 1.6
            new_weights["persona"] = 1.1
            new_weights["anima"] = 0.8
            new_weights["self"] = 0.7

        elif sound_type == "noise":
            # Moderate ambient noise - balanced with slight Persona emphasis
            new_weights["persona"] = 1.2

        # Smooth transition (don't snap weights)
        self.current_weights = self._interpolate_weights(
            self.current_weights, new_weights, alpha=0.1
        )

        # Publish weight update
        self.event_bus.publish(
            "archetypes.weights.updated", {"weights": self.current_weights.copy()}
        )

    def get_weight(self, archetype_name: str) -> float:
        """Get current weight for archetype.

        Args:
            archetype_name: Name of archetype

        Returns:
            Current weight
        """
        return self.current_weights.get(archetype_name, 1.0)

    def _interpolate_weights(
        self, current: dict[str, float], target: dict[str, float], alpha: float
    ) -> dict[str, float]:
        """Smooth weight transitions.

        Args:
            current: Current weights
            target: Target weights
            alpha: Interpolation factor (0-1)

        Returns:
            Interpolated weights
        """
        return {name: current[name] * (1 - alpha) + target[name] * alpha for name in current}
