"""Base archetype class."""

from abc import ABC, abstractmethod
from typing import Any

from sociopsi.llm.ollama_client import OllamaClient


class Archetype(ABC):
    """Base class for Jungian archetypes."""

    def __init__(self, name: str, llm_client: OllamaClient) -> None:
        """Initialize archetype.

        Args:
            name: Name of the archetype
            llm_client: LLM client for generating voices
        """
        self.name = name
        self.llm_client = llm_client

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt defining archetype's voice.

        Returns:
            System prompt string
        """
        pass

    async def generate_voice(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str = "",
    ) -> str:
        """Generate archetypal voice based on drives and context.

        Args:
            drive_state: Current drive states
            context: Additional context

        Returns:
            Generated archetypal voice
        """
        prompt = self._build_prompt(drive_state, context)
        response = await self.llm_client.generate(
            prompt,
            temperature=self.get_temperature(),
            max_tokens=100,
        )
        return response.strip()

    def _build_prompt(self, drive_state: dict[str, dict[str, Any]], context: str) -> str:
        """Build prompt for archetype.

        Args:
            drive_state: Current drive states
            context: Additional context

        Returns:
            Complete prompt string
        """
        system = self.get_system_prompt()

        drive_summary = "\n".join(
            f"- {name}: {state['value']:.2f} ({'satisfied' if not state['below_threshold'] else 'needs attention'})"
            for name, state in drive_state.items()
        )

        prompt = f"""{system}

Current drive states:
{drive_summary}

{f"Context: {context}" if context else ""}

Respond in 1-2 sentences from your archetypal perspective:"""

        return prompt

    def get_temperature(self) -> float:
        """Get temperature for this archetype.

        Returns:
            Temperature value
        """
        return 0.7

    async def generate(self, prompt: str) -> str:
        """Generate response using the archetype's personality.

        Args:
            prompt: Prompt to respond to

        Returns:
            Generated response
        """
        full_prompt = f"{self.get_system_prompt()}\n\n{prompt}"
        response = await self.llm_client.generate(
            full_prompt,
            temperature=self.get_temperature(),
            max_tokens=150,
        )
        return response.strip()
