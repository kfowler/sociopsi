"""Ego - conscious mediator of archetypal voices."""

import logging
from typing import TYPE_CHECKING, Any

from sociopsi.llm import chat_with_retry

if TYPE_CHECKING:
    from sociopsi.archetypes.base import Archetype

logger = logging.getLogger(__name__)


class Ego:
    """Conscious mediator integrating archetypal voices.

    The Ego listens to all archetypal perspectives and synthesizes them
    into coherent thoughts and decisions. It represents the conscious
    "I" that emerges from the interplay of deeper psychological forces.
    """

    def __init__(
        self,
        archetypes: dict[str, Archetype],
        model: str = "sociopsi-mid",
    ) -> None:
        """Initialize Ego.

        Args:
            archetypes: Dictionary of archetype instances
            model: Ollama model to use for mediation
        """
        self.archetypes = archetypes
        self.model = model
        self.strength: float = 0.5  # Ego strength develops over time
        self.last_harmony: float = 0.5

    def mediate(
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
        if not archetypal_voices:
            return ""

        # Build mediation prompt
        voices_text = "\n".join(
            f"[{name.upper()}] {voice}"
            for name, voice in archetypal_voices.items()
            if voice  # Skip empty voices
        )

        if not voices_text:
            return ""

        # Get individuation level (psychological integration)
        individuation = drive_state.get("individuation", {}).get("value", 0.5)

        prompt = f"""You are the Ego - the conscious mediator of internal archetypal voices.
Your role is to integrate different perspectives into a coherent, authentic thought.

Your ego strength: {self.strength:.2f}
Individuation level (psychological integration): {individuation:.2f}

Internal voices:
{voices_text}

Integrate these perspectives into a single coherent thought (1-2 sentences).
Acknowledge the different viewpoints but find a balanced path forward.
Don't just summarize - synthesize into your own voice as the conscious "I".

IMPORTANT: Respond with ONLY plain text. No JSON, no formatting, no code blocks. Just your integrated thought:"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.6},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error in Ego mediation: {e}")
            return ""

    def calculate_harmony(self, archetypal_voices: dict[str, str]) -> float:
        """Calculate harmony/agreement level between voices (0-1).

        Higher harmony = voices are in agreement
        Lower harmony = voices are in conflict

        Args:
            archetypal_voices: Dictionary of archetype voices

        Returns:
            Harmony score (0=conflict, 1=harmony)
        """
        if not archetypal_voices:
            return 0.5

        # Simple heuristic based on voice count and length variance
        # More sophisticated: use embeddings for semantic similarity
        voices = [v for v in archetypal_voices.values() if v]

        if len(voices) < 2:
            return 0.5

        # Base harmony
        base_harmony = 0.5

        # More voices participating = more potential for integration
        participation_bonus = min(0.15, len(voices) * 0.05)

        # Check for conflict indicators (negations, contradictions)
        conflict_words = [
            "but",
            "however",
            "despite",
            "although",
            "against",
            "don't",
            "won't",
            "shouldn't",
        ]
        conflict_count = sum(
            1 for voice in voices for word in conflict_words if word.lower() in voice.lower()
        )
        conflict_penalty = min(0.3, conflict_count * 0.05)

        harmony = max(0.1, min(1.0, base_harmony + participation_bonus - conflict_penalty))
        self.last_harmony = harmony
        return harmony

    def develop(self, harmony: float) -> None:
        """Develop ego strength based on integration quality.

        High harmony = good integration = ego strengthens
        Low harmony = poor integration = ego may weaken

        Args:
            harmony: Harmony level from last mediation
        """
        if harmony > 0.7:
            # Good integration strengthens ego
            self.strength = min(1.0, self.strength + 0.01)
        elif harmony < 0.3:
            # Poor integration may weaken ego slightly
            self.strength = max(0.1, self.strength - 0.005)

    def classify_command(
        self,
        command: str,
        interpretations: dict[str, str],
        drive_state: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Classify a command based on archetypal interpretations.

        Args:
            command: Original command text
            interpretations: Dictionary of archetype interpretations
            drive_state: Current drive states

        Returns:
            Classification dict with type (query/action/goal) and details
        """
        interp_text = "\n".join(
            f"[{name.upper()}] {interp}" for name, interp in interpretations.items() if interp
        )

        prompt = f"""You are the Ego synthesizing archetypal perspectives on a command.

Command: "{command}"

Archetypal interpretations:
{interp_text}

Classify this command:
1. QUERY - Asking for information (about drives, state, thoughts, etc.)
2. ACTION - Requesting an immediate action
3. GOAL - Requesting a new goal or objective

Respond with JSON: {{"type": "query|action|goal", "details": "brief description"}}"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3},  # Low temp for classification
            )
            content = response["message"]["content"].strip()

            # Parse JSON response
            import json

            # Try to extract JSON from response
            if "{" in content and "}" in content:
                json_str = content[content.index("{") : content.rindex("}") + 1]
                return json.loads(json_str)
            else:
                return {"type": "query", "details": content}

        except Exception as e:
            logger.error(f"Error in command classification: {e}")
            return {"type": "query", "details": command}

    def select_goal(
        self,
        proposals: dict[str, str],
        drive_state: dict[str, dict[str, Any]],
    ) -> str | None:
        """Select the best goal from archetypal proposals.

        Args:
            proposals: Dictionary of archetype goal proposals
            drive_state: Current drive states

        Returns:
            Selected goal, or None if no valid proposals
        """
        if not proposals:
            return None

        proposals_text = "\n".join(
            f"[{name.upper()}] {proposal}" for name, proposal in proposals.items() if proposal
        )

        if not proposals_text:
            return None

        # Find most urgent drives
        urgent_drives = [
            name for name, state in drive_state.items() if state.get("below_threshold", False)
        ]

        prompt = f"""You are the Ego selecting a goal from archetypal proposals.

Urgent drives needing attention: {", ".join(urgent_drives) if urgent_drives else "none"}

Proposed goals:
{proposals_text}

Select the most appropriate goal that balances urgency and feasibility.
Respond with just the selected goal (1 sentence):"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.5},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error in goal selection: {e}")
            # Fall back to first non-empty proposal
            for proposal in proposals.values():
                if proposal:
                    return proposal
            return None
