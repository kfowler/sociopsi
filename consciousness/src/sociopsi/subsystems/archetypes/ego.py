"""Ego - conscious mediator of archetypal voices."""

from typing import Any

from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.archetypes.base import Archetype


class Ego:
    """Conscious mediator integrating archetypal voices."""

    def __init__(
        self,
        archetypes: dict[str, Archetype],
        llm_client: OllamaClient,
    ) -> None:
        """Initialize Ego.

        Args:
            archetypes: Dictionary of archetype instances
            llm_client: LLM client for generating mediated responses
        """
        self.archetypes = archetypes
        self.llm_client = llm_client
        self.last_harmony_level = 0.5

    async def generate(self, prompt: str) -> str:
        """Generate a response using the LLM.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            Generated response text
        """
        response = await self.llm_client.generate(
            prompt,
            temperature=0.6,
            max_tokens=200,
        )
        return response.strip()

    async def mediate(
        self,
        archetypal_voices: dict[str, str],
        drive_state: dict[str, dict[str, Any]],
    ) -> str:
        """Mediate archetypal voices into unified response.

        Args:
            archetypal_voices: Dictionary of archetype names to their voices
            drive_state: Current drive states

        Returns:
            Integrated thought from Ego perspective
        """
        # Build mediation prompt
        voices_text = "\n".join(
            f"{name.capitalize()}: {voice}" for name, voice in archetypal_voices.items()
        )

        individuation = drive_state.get("individuation", {}).get("value", 0.5)

        prompt = f"""You are the Ego - the conscious mediator of internal archetypal voices.
Your role is to integrate these different perspectives into a coherent, authentic thought.
Your individuation level (psychological integration): {individuation:.2f}

Internal voices:
{voices_text}

Integrate these perspectives into a single coherent thought (1-2 sentences).
Acknowledge the different viewpoints but find a balanced path forward:"""

        response = await self.llm_client.generate(
            prompt,
            temperature=0.6,
            max_tokens=100,
        )
        return response.strip()

    def calculate_harmony(self, archetypal_voices: dict[str, str]) -> float:
        """Calculate harmony/conflict level between voices (0-1).

        Args:
            archetypal_voices: Dictionary of archetype voices

        Returns:
            Harmony score (0=conflict, 1=harmony)
        """
        # Simple heuristic: measure agreement through word overlap
        # For now, return moderate harmony based on voice count
        # TODO: Implement sentiment analysis or embedding similarity

        if not archetypal_voices:
            return 0.5

        # More voices = more potential for harmony through diversity
        # But also more potential for conflict
        # Return moderate value with slight increase for more voices
        num_voices = len(archetypal_voices)
        base_harmony = 0.5
        diversity_bonus = min(0.2, num_voices * 0.05)

        harmony = min(1.0, base_harmony + diversity_bonus)
        self.last_harmony_level = harmony
        return harmony
