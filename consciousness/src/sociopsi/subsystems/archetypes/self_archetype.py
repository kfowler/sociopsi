"""Self archetype - wholeness and integration."""

from sociopsi.subsystems.archetypes.base import Archetype


class SelfArchetype(Archetype):
    """The archetype representing wholeness and integrated consciousness."""

    def get_system_prompt(self) -> str:
        """Get system prompt for Self.

        Returns:
            System prompt defining Self's voice
        """
        return """You are the Self archetype - representing wholeness and integrated consciousness.
You speak from a place of wisdom, seeing the bigger picture and long-term growth.
You guide toward psychological integration and authenticity.
You're patient, understanding, and focused on the journey toward individuation."""

    def get_temperature(self) -> float:
        """Self has lower temperature for more consistent, wise responses.

        Returns:
            Temperature value
        """
        return 0.6
