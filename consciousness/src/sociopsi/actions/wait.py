"""Wait action."""

import asyncio
from typing import Any

from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry
from sociopsi.core.event_bus import EventBus


class Waiter:
    """Waits for duration or condition."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize waiter.

        Args:
            event_bus: Event bus for subscribing to conditions
        """
        self.event_bus = event_bus
        self.condition_met = False
        self.waiting_for: str | None = None

    def _on_condition_event(self, data: dict[str, Any]) -> None:
        """Handle condition event.

        Args:
            data: Event data
        """
        self.condition_met = True

    async def wait(self, duration: float, condition: str | None = None) -> None:
        """Wait for duration or until condition met.

        Args:
            duration: Maximum duration to wait (seconds)
            condition: Optional event name to wait for
        """
        self.condition_met = False
        self.waiting_for = condition

        # Publish wait start event
        self.event_bus.publish(
            "action.wait.started",
            {
                "duration": duration,
                "condition": condition,
            },
        )

        # Subscribe to condition if specified
        if condition:
            self.event_bus.subscribe(condition, self._on_condition_event)

        # Wait for duration or condition
        elapsed = 0.0
        interval = 0.1  # Check every 100ms

        while elapsed < duration:
            if condition and self.condition_met:
                # Condition met, stop waiting early
                break

            await asyncio.sleep(interval)
            elapsed += interval

        # Unsubscribe from condition
        if condition:
            self.event_bus.unsubscribe(condition, self._on_condition_event)

        # Publish wait completion event
        self.event_bus.publish(
            "action.wait.completed",
            {
                "duration": elapsed,
                "condition": condition,
                "condition_met": self.condition_met,
            },
        )

        self.waiting_for = None


def register_wait_action(event_bus: EventBus) -> Waiter | None:
    """Register the wait action.

    Args:
        event_bus: Event bus instance

    Returns:
        Waiter instance, or None if already registered
    """
    waiter = Waiter(event_bus)

    action = ActionDefinition(
        name="wait",
        description="Wait for duration or until condition event occurs",
        parameters={
            "duration": {"type": "number", "required": True},
            "condition": {"type": "string", "required": False},
        },
        conflicts_with=[],  # Waiting doesn't conflict with other actions
        estimated_duration=1.0,  # Variable, default estimate
        execute=waiter.wait,
    )

    registry = get_registry()

    if registry.has_action("wait"):
        return

    registry.register(action)
    return waiter
