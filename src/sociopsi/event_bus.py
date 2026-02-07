"""Event bus for inter-subsystem communication.

Provides loose coupling between subsystems via publish/subscribe pattern.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

type EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Central event bus for publish/subscribe communication."""

    _instance: EventBus | None = None

    def __init__(self) -> None:
        """Initialize event bus."""
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> EventBus:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Dot-separated event name (e.g., "perception.face_detected")
            handler: Callback function that receives event data dict
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Event name to unsubscribe from
            handler: Previously subscribed handler
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed from {event_type}")
            except ValueError:
                pass  # Handler not found, ignore

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Publish an event to all subscribers.

        Args:
            event_type: Event name
            data: Event payload as dictionary (default empty dict)
        """
        if data is None:
            data = {}

        handlers = self._subscribers.get(event_type, [])
        if handlers:
            logger.debug(f"Publishing {event_type} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                # Log but don't crash - one handler failure shouldn't break others
                logger.error(f"Error in event handler for {event_type}: {e}")

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._subscribers.clear()


# Convenience function for global event bus
def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return EventBus.get_instance()
