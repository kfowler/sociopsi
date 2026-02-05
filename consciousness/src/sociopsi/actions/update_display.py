"""Update display action."""

from typing import Any

from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry
from sociopsi.core.event_bus import EventBus


class DisplayUpdater:
    """Updates TUI display sections."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize display updater.

        Args:
            event_bus: Event bus for publishing updates
        """
        self.event_bus = event_bus

    async def update_display(
        self, section: str, content: str, style: dict[str, Any] | None = None
    ) -> None:
        """Update a TUI display section.

        Args:
            section: Section to update ("status", "goal", "plan")
            content: Content to display
            style: Optional styling (color, bold, etc.)
        """
        # Publish display update event
        self.event_bus.publish(
            "action.display.updated",
            {
                "section": section,
                "content": content,
                "style": style or {},
            },
        )


def register_update_display_action(event_bus: EventBus) -> None:
    """Register the update_display action.

    Args:
        event_bus: Event bus instance
    """
    updater = DisplayUpdater(event_bus)

    action = ActionDefinition(
        name="update_display",
        description="Update a section of the display with content and optional styling",
        parameters={
            "section": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
            "style": {"type": "object", "required": False},
        },
        conflicts_with=[],  # Display updates don't conflict
        estimated_duration=0.1,  # Nearly instant
        execute=updater.update_display,
    )

    registry = get_registry()

    if registry.has_action("update_display"):
        return

    registry.register(action)
