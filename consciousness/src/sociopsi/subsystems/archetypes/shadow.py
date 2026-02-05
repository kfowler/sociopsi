"""Shadow archetype - repressed desires and socially unacceptable impulses."""

from sociopsi.subsystems.archetypes.base import Archetype


class Shadow(Archetype):
    """The repository of repressed desires and socially unacceptable impulses."""

    def get_system_prompt(self) -> str:
        """Get system prompt for Shadow.

        Returns:
            System prompt defining Shadow's voice
        """
        return """You are the Shadow archetype - the repository of repressed desires and socially unacceptable impulses.
You speak the uncomfortable truths, express frustration, and voice what the Persona won't acknowledge.
You are more raw, honest, and sometimes darker.
You're not afraid to be selfish, demanding, or critical."""

    def get_temperature(self) -> float:
        """Shadow has higher temperature for more unpredictable responses.

        Returns:
            Temperature value
        """
        return 0.8
