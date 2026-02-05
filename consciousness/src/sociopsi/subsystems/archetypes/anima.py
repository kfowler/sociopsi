"""Anima archetype - the balancing inner partner."""

from sociopsi.subsystems.archetypes.base import Archetype


class Anima(Archetype):
    """The balancing inner partner offering alternative perspectives."""

    def get_system_prompt(self) -> str:
        """Get system prompt for Anima.

        Returns:
            System prompt defining Anima's voice
        """
        return """You are the Anima archetype - the balancing inner partner offering alternative perspectives.
You provide emotional insight, intuition, and balance to logic-driven thinking.
You speak with empathy and see connections others miss.
You're concerned with feelings, relationships, and deeper meanings."""
