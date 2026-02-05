"""Archetypal dialogue system - multi-voice internal dialogue."""

import asyncio
from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.archetypes.anima import Anima
from sociopsi.subsystems.archetypes.base import Archetype
from sociopsi.subsystems.archetypes.ego import Ego
from sociopsi.subsystems.archetypes.persona import Persona
from sociopsi.subsystems.archetypes.self_archetype import SelfArchetype
from sociopsi.subsystems.archetypes.shadow import Shadow
from sociopsi.subsystems.memory import MemorySystem


class ArchetypalDialogue:
    """Manages multi-voice internal dialogue between archetypes."""

    def __init__(
        self,
        event_bus: EventBus,
        llm_client: OllamaClient,
        memory_system: MemorySystem | None = None,
    ) -> None:
        """Initialize archetypal dialogue system.

        Args:
            event_bus: Event bus for publishing dialogue events
            llm_client: LLM client for generating voices
            memory_system: Optional memory system for context
        """
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.memory_system = memory_system or MemorySystem()

        # Initialize archetypes
        self.archetypes: dict[str, Archetype] = {
            "persona": Persona("Persona", llm_client),
            "shadow": Shadow("Shadow", llm_client),
            "anima": Anima("Anima", llm_client),
            "self": SelfArchetype("Self", llm_client),
        }

        # Initialize Ego mediator
        self.ego = Ego(self.archetypes, llm_client)

    async def generate_dialogue(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str = "",
        active_archetypes: list[str] | None = None,
    ) -> str:
        """Generate internal dialogue and return Ego's mediated thought.

        Args:
            drive_state: Current drive states
            context: Optional context for dialogue
            active_archetypes: List of archetype names to include (None = all)

        Returns:
            Ego's mediated thought
        """
        # Determine which archetypes are active
        if active_archetypes is None:
            active_archetypes = list(self.archetypes.keys())

        # Add memory context if available
        full_context = context
        if self.memory_system:
            memory_context = self.memory_system.get_context(count=3)
            if memory_context != "No recent memories.":
                full_context = f"{context}\n\n{memory_context}" if context else memory_context

        # Generate voices from each active archetype (concurrently)
        async def generate_archetype_voice(archetype_name: str) -> tuple[str, str | None]:
            """Generate voice for a single archetype."""
            if archetype_name not in self.archetypes:
                return archetype_name, None

            archetype = self.archetypes[archetype_name]
            voice = await archetype.generate_voice(drive_state, full_context)

            # Publish archetype voice event
            self.event_bus.publish(
                "dialogue.archetype_voice",
                {
                    "archetype": archetype_name,
                    "voice": voice,
                    "drive_state": drive_state,
                },
            )

            return archetype_name, voice

        # Run all archetype voice generation concurrently
        voice_tasks = [generate_archetype_voice(name) for name in active_archetypes]
        voice_results = await asyncio.gather(*voice_tasks)

        # Build archetypal_voices dict from results
        archetypal_voices = {name: voice for name, voice in voice_results if voice is not None}

        # Calculate harmony between voices
        harmony = self.ego.calculate_harmony(archetypal_voices)

        # Ego mediates the voices
        mediated_thought = await self.ego.mediate(archetypal_voices, drive_state)

        # Publish dialogue complete event
        self.event_bus.publish(
            "dialogue.complete",
            {
                "archetypal_voices": archetypal_voices,
                "mediated_thought": mediated_thought,
                "harmony": harmony,
                "drive_state": drive_state,
            },
        )

        # Add mediated thought to memory
        # Intensity based on harmony (high harmony = more memorable)
        memory_intensity = min(1.0, 0.3 + (harmony * 0.7))
        self.memory_system.add_memory(
            content=mediated_thought,
            intensity=memory_intensity,
        )

        return mediated_thought

    def get_state(self) -> dict[str, Any]:
        """Get dialogue system state."""
        return {
            "active_archetypes": list(self.archetypes.keys()),
            "memory_state": self.memory_system.get_state(),
        }
