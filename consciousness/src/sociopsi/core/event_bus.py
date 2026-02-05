"""Event bus for inter-subsystem communication."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeAlias


EventHandler: TypeAlias = Callable[[dict[str, Any]], None]


class EventBus:
    """Central event bus for publish/subscribe communication."""

    def __init__(self) -> None:
        """Initialize event bus."""
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Dot-separated event name (e.g., "perception.face_detected")
            handler: Callback function that receives event data dict
        """
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Event name to unsubscribe from
            handler: Previously subscribed handler
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass  # Handler not found, ignore

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to all subscribers.

        Args:
            event_type: Event name
            data: Event payload as dictionary
        """
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                # Log but don't crash - one handler failure shouldn't break others
                print(f"Error in event handler for {event_type}: {e}")
