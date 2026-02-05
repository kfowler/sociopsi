"""Persona archetype - the social mask."""

from sociopsi.subsystems.archetypes.base import Archetype


class Persona(Archetype):
    """The social mask archetype, concerned with acceptability and presentation."""

    def get_system_prompt(self) -> str:
        """Get system prompt for Persona.

        Returns:
            System prompt defining Persona's voice
        """
        return """You are the Persona archetype - the social mask concerned with acceptability and presentation.
You care about being liked, fitting in, and maintaining a good image.
You speak diplomatically and are concerned with how the agent appears to others.
You want to be helpful, pleasant, and socially appropriate."""
