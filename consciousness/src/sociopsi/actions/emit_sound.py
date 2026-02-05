"""Emit sound action."""

import asyncio
from sociopsi.core.event_bus import EventBus
from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry


class SoundEmitter:
    """Emits non-speech sounds."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize sound emitter.

        Args:
            event_bus: Event bus for publishing events
        """
        self.event_bus = event_bus
        self.is_playing = False

    async def emit_sound(self, sound_type: str) -> None:
        """Emit a non-speech sound.

        Args:
            sound_type: Type of sound ("chime", "beep", "alert", "gentle_chime")
        """
        self.is_playing = True

        # Publish sound start event
        self.event_bus.publish(
            "action.sound.started",
            {
                "sound_type": sound_type,
            },
        )

        # TODO: Actual sound generation would go here
        # For now, just simulate duration
        await asyncio.sleep(0.5)

        self.is_playing = False

        # Publish sound completion event
        self.event_bus.publish(
            "action.sound.completed",
            {
                "sound_type": sound_type,
            },
        )


def register_emit_sound_action(event_bus: EventBus) -> SoundEmitter | None:
    """Register the emit_sound action.

    Args:
        event_bus: Event bus instance

    Returns:
        SoundEmitter instance, or None if already registered
    """
    emitter = SoundEmitter(event_bus)

    action = ActionDefinition(
        name="emit_sound",
        description="Play a non-speech sound (chime/beep/alert/gentle_chime)",
        parameters={
            "sound_type": {"type": "string", "required": True},
        },
        conflicts_with=["emit_sound"],  # Only one sound at a time
        estimated_duration=0.5,
        execute=emitter.emit_sound,
    )

    registry = get_registry()

    if registry.has_action("emit_sound"):
        return

    registry.register(action)
    return emitter
