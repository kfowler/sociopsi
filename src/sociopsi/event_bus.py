"""Event bus for inter-subsystem communication.

Provides loose coupling between subsystems via publish/subscribe pattern
with async queue-based dispatch.

publish() is non-blocking: events are enqueued to per-subscriber queues and
dispatched by a dedicated background thread. Priority events (survival/compulsive)
bypass the queue for immediate inline dispatch. Coalescable events (somatic
updates) only keep the latest value when published rapidly.
"""

import logging
import queue
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

type EventHandler = Callable[[dict[str, Any]], None]


@dataclass
class _Subscription:
    """A single handler subscribed to an event type."""

    event_type: str
    handler: EventHandler
    queue: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    # Coalesce slot: holds latest data for coalescable events.
    # Written by publishing thread, read/cleared by dispatcher thread.
    # Thread-safe under CPython GIL (simple attribute assignment).
    _coalesce_data: dict[str, Any] | None = field(default=None, repr=False)
    _coalesce_pending: bool = field(default=False, repr=False)


class EventBus:
    """Central event bus with async queue-based dispatch.

    Each subscriber gets its own queue. A dedicated dispatcher thread
    drains queues and calls handlers. publish() is non-blocking.

    Priority events (survival/compulsive) bypass the queue and dispatch
    immediately inline. Coalescable events (somatic updates) only keep
    the latest value — rapid publishes coalesce to one dispatch.

    When the dispatcher is not running (start() not called), publish()
    falls back to synchronous inline dispatch for backward compatibility.
    """

    _instance: EventBus | None = None

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[_Subscription]] = defaultdict(list)
        self._all_subs: list[_Subscription] = []
        self._lock = threading.Lock()

        # Priority: these event types dispatch immediately (skip queue)
        self._priority_types: set[str] = set()
        # Coalesce: these event types only keep latest value
        self._coalesce_types: set[str] = set()

        # Dispatcher thread
        self._running = False
        self._dispatcher: threading.Thread | None = None
        self._stop_event = threading.Event()

    @classmethod
    def get_instance(cls) -> EventBus:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance is not None:
            cls._instance.stop()
        cls._instance = None

    def start(self) -> None:
        """Start the dispatcher thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="event-bus-dispatcher",
        )
        self._dispatcher.start()
        logger.debug("Event bus dispatcher started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the dispatcher thread and drain remaining events."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._dispatcher is not None:
            self._dispatcher.join(timeout=timeout)
            self._dispatcher = None
        logger.debug("Event bus dispatcher stopped")

    def set_priority(self, *event_types: str) -> None:
        """Mark event types for immediate (non-queued) dispatch.

        Priority events skip the queue and call handlers inline in the
        publishing thread. Use for survival/compulsive events that must
        not be delayed.
        """
        self._priority_types.update(event_types)

    def set_coalesce(self, *event_types: str) -> None:
        """Mark event types for coalescing.

        When multiple events of a coalescable type are published rapidly,
        only the latest value is dispatched. Use for somatic updates.
        """
        self._coalesce_types.update(event_types)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Dot-separated event name (e.g., "perception.face_detected")
            handler: Callback function that receives event data dict
        """
        sub = _Subscription(event_type=event_type, handler=handler)
        with self._lock:
            self._subscriptions[event_type].append(sub)
            self._all_subs.append(sub)
        logger.debug(f"Subscribed to {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Event name to unsubscribe from
            handler: Previously subscribed handler
        """
        with self._lock:
            subs = self._subscriptions.get(event_type, [])
            for sub in subs:
                if sub.handler is handler:
                    subs.remove(sub)
                    self._all_subs.remove(sub)
                    logger.debug(f"Unsubscribed from {event_type}")
                    return

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Publish an event to all subscribers (non-blocking).

        Priority events dispatch inline immediately. Coalescable events
        store only the latest value. All other events are enqueued for
        the dispatcher thread.

        When the dispatcher is not running, falls back to synchronous dispatch.

        Args:
            event_type: Event name
            data: Event payload as dictionary (default empty dict)
        """
        if data is None:
            data = {}

        with self._lock:
            subs = list(self._subscriptions.get(event_type, []))

        if not subs:
            return

        logger.debug(f"Publishing {event_type} to {len(subs)} handlers")

        # Priority events: immediate inline dispatch
        if event_type in self._priority_types:
            for sub in subs:
                try:
                    sub.handler(data)
                except Exception as e:
                    logger.error(f"Error in priority handler for {event_type}: {e}")
            return

        # If dispatcher not running, synchronous fallback
        if not self._running:
            for sub in subs:
                try:
                    sub.handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
            return

        # Coalescable events: store latest in slot, mark pending
        if event_type in self._coalesce_types:
            for sub in subs:
                sub._coalesce_data = data
                sub._coalesce_pending = True
            return

        # Normal: enqueue to each subscriber's queue
        for sub in subs:
            sub.queue.put(data)

    def drain(self, timeout: float = 1.0) -> None:
        """Wait until all queued events are dispatched.

        Useful for testing and clean shutdown.

        Args:
            timeout: Maximum seconds to wait
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                all_empty = all(
                    sub.queue.empty() and not sub._coalesce_pending for sub in self._all_subs
                )
            if all_empty:
                return
            time.sleep(0.005)

    def clear(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
            self._all_subs.clear()

    def _dispatch_loop(self) -> None:
        """Dispatcher thread main loop.

        Round-robins through all subscriber queues, dispatching one event
        per subscriber per pass. Also checks coalesce slots. Sleeps briefly
        when no events are pending.
        """
        while self._running:
            dispatched = False

            with self._lock:
                subs = list(self._all_subs)

            for sub in subs:
                # Check coalesce slot first
                if sub._coalesce_pending:
                    data = sub._coalesce_data
                    sub._coalesce_data = None
                    sub._coalesce_pending = False
                    dispatched = True
                    if data is not None:
                        try:
                            sub.handler(data)
                        except Exception as e:
                            logger.error(f"Error in event handler for {sub.event_type}: {e}")

                # Check queue
                try:
                    data = sub.queue.get_nowait()
                    dispatched = True
                    try:
                        sub.handler(data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {sub.event_type}: {e}")
                except queue.Empty:
                    pass

            if not dispatched:
                # Wait briefly for new events or stop signal
                self._stop_event.wait(timeout=0.005)


# Convenience function for global event bus
def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return EventBus.get_instance()
