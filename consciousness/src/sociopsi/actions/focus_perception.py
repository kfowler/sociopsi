"""Focus perception action."""

from sociopsi.core.event_bus import EventBus
from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry


class PerceptionFocuser:
    """Directs attention to specific perception modalities."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize perception focuser.

        Args:
            event_bus: Event bus for publishing events
        """
        self.event_bus = event_bus
        self.current_focus: str = "camera"  # Default focus

    async def focus_perception(self, modality: str) -> None:
        """Direct attention to a perception modality.

        Args:
            modality: Modality to focus on ("camera", "audio", "physical")
        """
        self.current_focus = modality

        # Publish focus event
        self.event_bus.publish(
            "action.perception.focused",
            {
                "modality": modality,
            },
        )

    def get_current_focus(self) -> str:
        """Get currently focused modality.

        Returns:
            Current modality name
        """
        return self.current_focus


def register_focus_perception_action(event_bus: EventBus) -> PerceptionFocuser | None:
    """Register the focus_perception action.

    Args:
        event_bus: Event bus instance

    Returns:
        PerceptionFocuser instance, or None if already registered
    """
    focuser = PerceptionFocuser(event_bus)

    action = ActionDefinition(
        name="focus_perception",
        description="Direct attention to a specific perception modality (camera/audio/physical)",
        parameters={
            "modality": {"type": "string", "required": True},
        },
        conflicts_with=[],  # Focusing doesn't conflict with other actions
        estimated_duration=0.1,  # Instant
        execute=focuser.focus_perception,
    )

    registry = get_registry()

    if registry.has_action("focus_perception"):
        return

    registry.register(action)
    return focuser
