"""Base archetype class for Jungian internal dialogue."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from jung_agent.llm import chat_with_retry

logger = logging.getLogger(__name__)


class Archetype(ABC):
    """Base class for Jungian archetypes.

    Each archetype represents a distinct psychological voice with its own
    concerns, personality, and perspective on the agent's state.
    """

    def __init__(self, name: str, model: str = "jung-mid") -> None:
        """Initialize archetype.

        Args:
            name: Name of the archetype
            model: Ollama model to use for generation
        """
        self.name = name
        self.model = model
        self.influence_weight: float = 0.25  # Default equal weight

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt defining archetype's voice.

        Returns:
            System prompt string defining personality and concerns
        """
        pass

    def get_temperature(self) -> float:
        """Get temperature for this archetype's generation.

        Returns:
            Temperature value (higher = more creative/random)
        """
        return 0.7

    def generate_voice(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str = "",
    ) -> str:
        """Generate archetypal voice based on drives and context.

        Args:
            drive_state: Current drive states {name: {value, threshold, below_threshold}}
            context: Additional context (somatic state, recent events, etc.)

        Returns:
            Generated archetypal voice (1-2 sentences)
        """
        prompt = self._build_prompt(drive_state, context)

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": self.get_temperature()},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error generating {self.name} voice: {e}")
            return ""

    def _build_prompt(self, drive_state: dict[str, dict[str, Any]], context: str) -> str:
        """Build prompt for archetype voice generation.

        Args:
            drive_state: Current drive states
            context: Additional context

        Returns:
            Complete prompt string
        """
        system = self.get_system_prompt()

        # Format drive summary
        drive_lines = []
        for name, state in drive_state.items():
            value = state.get("value", 0.5)
            below = state.get("below_threshold", False)
            status = "URGENT" if below else "satisfied"
            drive_lines.append(f"  {name}: {value:.2f} ({status})")

        drive_summary = "\n".join(drive_lines)

        prompt = f"""{system}

Current drive states:
{drive_summary}

{f"Context: {context}" if context else ""}

IMPORTANT: Respond with ONLY 1-2 plain text sentences. No JSON, no formatting, no code blocks. Just speak naturally as this psychological voice:"""

        return prompt

    def interpret_command(self, command: str, drive_state: dict[str, dict[str, Any]]) -> str:
        """Interpret a user command from this archetype's perspective.

        Args:
            command: User's command text
            drive_state: Current drive states

        Returns:
            Archetypal interpretation of the command
        """
        system = self.get_system_prompt()

        prompt = f"""{system}

A command has been received: "{command}"

Interpret this command from your archetypal perspective. What does it mean?
What should be done? What concerns do you have?

Respond in 1-2 sentences:"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": self.get_temperature()},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error in {self.name} command interpretation: {e}")
            return ""

    def propose_goal(self, low_drives: list[str], drive_state: dict[str, dict[str, Any]]) -> str:
        """Propose a goal to address low drives.

        Args:
            low_drives: List of drive names that are below threshold
            drive_state: Current drive states

        Returns:
            Proposed goal description
        """
        system = self.get_system_prompt()

        drives_text = ", ".join(low_drives)

        prompt = f"""{system}

The following drives need attention: {drives_text}

From your archetypal perspective, propose a specific goal that would help
satisfy these drives. Be concrete and actionable.

Respond with a single goal in 1 sentence:"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": self.get_temperature()},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error in {self.name} goal proposal: {e}")
            return ""
