"""Command processor with archetypal consultation."""

import asyncio
import json
import random
import time
from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.archetypes.base import Archetype
from sociopsi.subsystems.archetypes.ego import Ego
from sociopsi.subsystems.drives import DriveSystem


class CommandProcessor:
    """Processes commands through archetypal consultation."""

    def __init__(
        self,
        event_bus: EventBus,
        archetypes: list[Archetype],
        ego: Ego | None,
        drive_system: DriveSystem,
    ) -> None:
        """Initialize command processor.

        Args:
            event_bus: Event bus for pub/sub
            archetypes: List of archetypal voices
            ego: Ego mediator
            drive_system: Drive system for state calculation
        """
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.ego = ego
        self.drive_system = drive_system
        self.last_harmony = 0.5  # Default mid-range

        event_bus.subscribe("command.received", self._on_command_sync)

    def _on_command_sync(self, data: dict[str, Any]) -> None:
        """Synchronous wrapper for async handler."""
        import asyncio

        asyncio.create_task(self.on_command(data))

    async def on_command(self, data: dict[str, Any]) -> None:
        """Handle incoming command.

        Args:
            data: Command data with 'text', 'source', 'timestamp'
        """
        command_text = data["text"]

        # Calculate psychological state
        state = self._calculate_state()
        consultation_duration = self._get_consultation_duration(state)

        # Archetypal interpretation
        interpretations = await self._archetypal_interpretation(command_text, consultation_duration)

        # Ego synthesis
        classification = await self._ego_classification(command_text, interpretations)

        # Route to handler
        await self._route_command(classification)

    def _calculate_state(self) -> str:
        """Determine psychological state: threat/normal/calm.

        Returns:
            State string: "threat", "normal", or "calm"
        """
        # Calculate average drive level
        if not self.drive_system.drives:
            return "normal"

        avg_level = sum(d.value for d in self.drive_system.drives.values()) / len(
            self.drive_system.drives
        )
        harmony = self.last_harmony

        # Threat: low drives or low harmony
        if avg_level < 0.3 or harmony < 0.3:
            return "threat"
        # Calm: high drives and high harmony
        elif avg_level > 0.7 and harmony > 0.7:
            return "calm"
        # Normal: everything else
        else:
            return "normal"

    def _get_consultation_duration(self, state: str) -> float:
        """Map state to consultation duration.

        Args:
            state: Psychological state

        Returns:
            Duration in seconds
        """
        durations: dict[str, tuple[float, float]] = {
            "threat": (0.5, 1.0),
            "normal": (1.0, 2.0),
            "calm": (2.0, 4.0),
        }
        min_dur, max_dur = durations[state]
        return random.uniform(min_dur, max_dur)

    async def _archetypal_interpretation(
        self, command: str, duration: float
    ) -> list[dict[str, Any]]:
        """Each archetype interprets command intent.

        Args:
            command: User command text
            duration: How long consultation should take

        Returns:
            List of archetypal interpretations
        """
        interpretations: list[dict[str, Any]] = []

        for archetype in self.archetypes:
            prompt = f"""The user said: "{command}"

From your perspective as {archetype.name}, interpret this command:
- What does the user want?
- What is their intent/motivation?
- Is this a query (asking for information), an action (do something), or a goal (pursue over time)?

Respond in 1-2 sentences."""

            response = await archetype.generate(prompt)

            interpretations.append(
                {"archetype": archetype.name, "interpretation": response, "timestamp": time.time()}
            )

        # Simulate consultation duration
        await asyncio.sleep(duration)

        return interpretations

    async def _ego_classification(
        self, command: str, interpretations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Ego synthesizes archetypal perspectives into classification.

        Args:
            command: User command text
            interpretations: List of archetypal interpretations

        Returns:
            Classification dict with type, intent, parameters, confidence
        """
        perspectives = "\n".join(
            [f"- {i['archetype']}: {i['interpretation']}" for i in interpretations]
        )

        prompt = f"""User command: "{command}"

Archetypal perspectives:
{perspectives}

Synthesize these perspectives into a classification:
- Type: query | action | goal
- Intent: (one sentence describing what user wants)
- Parameters: (extract any relevant parameters like drive names, values, etc.)
- Confidence: (0-1, how clear is this classification)

Format as JSON."""

        if self.ego is None:
            return {"type": "unknown", "intent": command, "parameters": {}, "confidence": 0.0}

        response = await self.ego.generate(prompt)
        classification = self._parse_classification(response)

        self.event_bus.publish("command.classified", classification)
        return classification

    def _parse_classification(self, response: str) -> dict[str, Any]:
        """Parse LLM classification response.

        Args:
            response: LLM response (should be JSON)

        Returns:
            Classification dict
        """
        try:
            # Try to parse as JSON
            parsed = json.loads(response)
            return {
                "type": parsed.get("type", "query"),
                "intent": parsed.get("intent", "Unknown intent"),
                "parameters": parsed.get("parameters", {}),
                "confidence": parsed.get("confidence", 0.5),
            }
        except json.JSONDecodeError:
            # Fallback for non-JSON responses
            return {
                "type": "query",
                "intent": response[:100],  # First 100 chars
                "parameters": {},
                "confidence": 0.5,
            }

    async def _route_command(self, classification: dict[str, Any]) -> None:
        """Route command to appropriate handler.

        Args:
            classification: Command classification with type
        """
        cmd_type = classification["type"]

        if cmd_type == "query":
            self.event_bus.publish("command.query", classification)
        elif cmd_type == "action":
            self.event_bus.publish("command.action", classification)
        elif cmd_type == "goal":
            self.event_bus.publish("command.goal", classification)
