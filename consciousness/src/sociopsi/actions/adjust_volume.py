"""Adjust volume action."""

from sociopsi.core.event_bus import EventBus
from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry
from sociopsi.actions.speak import SpeechAction


class VolumeAdjuster:
    """Adjusts TTS volume."""

    def __init__(self, event_bus: EventBus, speech_action: SpeechAction) -> None:
        """Initialize volume adjuster.

        Args:
            event_bus: Event bus for publishing events
            speech_action: Speech action to adjust volume for
        """
        self.event_bus = event_bus
        self.speech_action = speech_action

    async def adjust_volume(self, level: float) -> None:
        """Adjust TTS volume.

        Args:
            level: Volume level (0.0 to 1.0)
        """
        # Clamp to valid range
        level = max(0.0, min(1.0, level))

        # Update speech action volume
        self.speech_action.set_volume(level)

        # Publish volume adjustment event
        self.event_bus.publish(
            "action.volume.adjusted",
            {
                "level": level,
            },
        )


def register_adjust_volume_action(event_bus: EventBus, speech_action: SpeechAction) -> None:
    """Register the adjust_volume action.

    Args:
        event_bus: Event bus instance
        speech_action: Speech action instance
    """
    adjuster = VolumeAdjuster(event_bus, speech_action)

    action = ActionDefinition(
        name="adjust_volume",
        description="Adjust text-to-speech volume level (0.0 to 1.0)",
        parameters={
            "level": {"type": "number", "required": True},
        },
        conflicts_with=[],  # Volume adjustment doesn't conflict
        estimated_duration=0.1,  # Instant
        execute=adjuster.adjust_volume,
    )

    registry = get_registry()

    if registry.has_action("adjust_volume"):
        return

    registry.register(action)
