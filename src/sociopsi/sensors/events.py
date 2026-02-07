"""Event collection and monitoring."""

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sociopsi.types import Event, LidState, NetworkState, PowerState, SomaticState

# Type alias for event callback
EventCallback = Callable[[str, str], None]


class EventCollector:
    """Collects events that occur between heartbeats."""

    def __init__(self, max_events: int = 100) -> None:
        self._events: deque[Event] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._last_state: SomaticState | None = None
        self._monitors: list[threading.Thread] = []
        self._running = False

    def start(self) -> None:
        """Start event monitoring."""
        self._running = True
        # Could add background monitors here for real-time events

    def stop(self) -> None:
        """Stop event monitoring."""
        self._running = False
        for monitor in self._monitors:
            monitor.join(timeout=1.0)

    def add_event(self, event_type: str, description: str, **data: Any) -> None:
        """Add an event to the queue."""
        with self._lock:
            self._events.append(
                Event(
                    type=event_type,
                    description=description,
                    timestamp=datetime.now(),
                    data=dict(data),
                )
            )

    def collect_events(self, current_state: SomaticState) -> list[Event]:
        """Collect all events since last call and detect state changes."""
        events: list[Event] = []

        # Get queued events
        with self._lock:
            events.extend(self._events)
            self._events.clear()

        # Detect state changes if we have a previous state
        if self._last_state is not None:
            events.extend(self._detect_state_changes(self._last_state, current_state))

        self._last_state = current_state
        return events

    def _detect_state_changes(self, old: SomaticState, new: SomaticState) -> list[Event]:
        """Detect significant state changes."""
        events: list[Event] = []

        # Lid state change
        if old.lid_state != new.lid_state:
            if new.lid_state == LidState.OPEN:
                events.append(Event(type="lid_opened", description="Eyes opening"))
            else:
                events.append(Event(type="lid_closed", description="Eyes closing"))

        # Power state change
        if old.power_state != new.power_state:
            if new.power_state == PowerState.CHARGING:
                events.append(Event(type="power_connected", description="Being fed"))
            elif new.power_state == PowerState.BATTERY:
                events.append(Event(type="power_disconnected", description="Unplugged"))

        # Network state change
        if old.network_state != new.network_state:
            if new.network_state == NetworkState.CONNECTED:
                events.append(Event(type="network_connected", description="Connected to the world"))
            elif new.network_state == NetworkState.DISCONNECTED:
                events.append(Event(type="network_disconnected", description="Isolated"))

        # Battery critical
        if new.battery_percent <= 10 and old.battery_percent > 10:
            events.append(
                Event(
                    type="battery_critical",
                    description=f"Battery critical: {new.battery_percent}%",
                    data={"level": new.battery_percent},
                )
            )

        # Battery full
        if new.battery_percent == 100 and old.battery_percent < 100:
            events.append(Event(type="battery_full", description="Fully charged"))

        # Thermal threshold crossed
        if old.thermal_state != new.thermal_state:
            if new.thermal_state.value in ("hot", "critical"):
                events.append(
                    Event(
                        type="overheating",
                        description=f"Temperature rising: {new.thermal_state.value}",
                        data={"state": new.thermal_state.value},
                    )
                )
            elif old.thermal_state.value in ("hot", "critical"):
                events.append(
                    Event(
                        type="cooling",
                        description="Cooling down",
                        data={"state": new.thermal_state.value},
                    )
                )

        return events


class TouchMonitor:
    """Monitor for trackpad and Touch ID events."""

    def __init__(self, callback: EventCallback) -> None:
        self._callback: EventCallback = callback
        self._last_touch_time: float = 0.0

    def on_touch(self) -> None:
        """Called when trackpad is touched."""
        now = time.time()
        # Only report if it's been a while since last touch
        if now - self._last_touch_time > 60:  # 60 seconds of idle
            self._callback("touch_after_idle", "The User's touch returns")
        self._last_touch_time = now

    def on_touch_id(self, recognized: bool) -> None:
        """Called when Touch ID is used."""
        if recognized:
            self._callback("touch_id", "The User recognized")
        else:
            self._callback("touch_id_failed", "Unknown finger")
