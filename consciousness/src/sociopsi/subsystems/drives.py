"""Drive system - homeostatic needs."""

from collections import deque
from dataclasses import dataclass, field
from time import time
from typing import Any, Mapping

from sociopsi.core.config import Config
from sociopsi.core.event_bus import EventBus


@dataclass
class Drive:
    """A single homeostatic drive."""

    name: str
    decay_rate: float
    base_threshold: float
    is_core: bool = True
    modifiable: bool = False

    value: float = 1.0  # 0.0 to 1.0
    last_satisfied: float = field(default_factory=time)
    satisfaction_history: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    time_below_threshold: float = 0.0

    # Track for threshold crossing events
    _was_below_threshold: bool = False

    def decay(self, dt: float) -> None:
        """Decay drive value over time.

        Args:
            dt: Time delta in seconds
        """
        self.value = max(0.0, self.value - (self.decay_rate * dt))

    def satisfy(self, amount: float, quality: float = 1.0) -> None:
        """Satisfy drive by some amount.

        Args:
            amount: Base satisfaction amount
            quality: Quality multiplier (for future context-aware satisfaction)
        """
        actual_gain = amount * quality
        self.value = min(1.0, self.value + actual_gain)
        self.last_satisfied = time()
        self.satisfaction_history.append(time())

    def is_below_threshold(self, effective_threshold: float | None = None) -> bool:
        """Check if drive is below threshold.

        Args:
            effective_threshold: Override threshold (for physical state modulation)

        Returns:
            True if below threshold
        """
        threshold = effective_threshold if effective_threshold is not None else self.base_threshold
        return self.value < threshold

    def get_state(self) -> dict[str, Any]:
        """Get drive state as dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.base_threshold,
            "below_threshold": self.is_below_threshold(),
            "time_below_threshold": self.time_below_threshold,
        }


class DriveSystem:
    """Manages all homeostatic drives."""

    def __init__(self, event_bus: EventBus, config: Config | None = None) -> None:
        """Initialize drive system.

        Args:
            event_bus: Event bus for publishing drive events
            config: Configuration (uses default if None)
        """
        self.event_bus = event_bus
        self.config = config or Config()
        self.drives: dict[str, Drive] = {}

        self._initialize_drives()

    def _initialize_drives(self) -> None:
        """Initialize drives from configuration."""
        # Core drives: affiliation, nurturing, and individuation
        for drive_name in ["affiliation", "nurturing", "individuation"]:
            drive_config = self.config.get_drive_config(drive_name)
            self.drives[drive_name] = Drive(
                name=drive_name,
                decay_rate=drive_config["decay_rate"],
                base_threshold=drive_config["base_threshold"],
                is_core=drive_config.get("is_core", True),
                modifiable=False,
            )

    def update(self, dt: float, physical_state: Mapping[str, Any] | None = None) -> None:
        """Update all drives.

        Args:
            dt: Time delta in seconds
            physical_state: Optional physical state for threshold modulation
        """
        for drive in self.drives.values():
            # Store previous state
            was_below = drive.is_below_threshold()

            # Decay drive
            drive.decay(dt)

            # Update time below threshold
            if drive.is_below_threshold():
                drive.time_below_threshold += dt
            else:
                drive.time_below_threshold = 0.0

            # Check for threshold crossing
            now_below = drive.is_below_threshold()
            if now_below and not was_below:
                self.event_bus.publish(
                    "drives.threshold_crossed",
                    {
                        "drive_name": drive.name,
                        "value": drive.value,
                        "direction": "below",
                    },
                )
            elif not now_below and was_below:
                self.event_bus.publish(
                    "drives.threshold_crossed",
                    {
                        "drive_name": drive.name,
                        "value": drive.value,
                        "direction": "above",
                    },
                )

            # Publish update event
            self.event_bus.publish(
                "drives.updated",
                {
                    "drive_name": drive.name,
                    "value": drive.value,
                    "below_threshold": now_below,
                },
            )

    def satisfy_drive(self, drive_name: str, amount: float, quality: float = 1.0) -> None:
        """Satisfy a specific drive.

        Args:
            drive_name: Name of drive to satisfy
            amount: Satisfaction amount
            quality: Quality multiplier
        """
        if drive_name in self.drives:
            self.drives[drive_name].satisfy(amount, quality)

    def get_state(self) -> dict[str, dict[str, Any]]:
        """Get state of all drives."""
        return {name: drive.get_state() for name, drive in self.drives.items()}

    def update_individuation(self, harmony: float) -> None:
        """Update individuation drive based on archetypal harmony.

        Args:
            harmony: Harmony level between archetypes (0-1)
        """
        if "individuation" in self.drives:
            # High harmony satisfies individuation
            if harmony > 0.7:
                self.satisfy_drive("individuation", amount=0.05)
            elif harmony < 0.3:
                # Low harmony can slightly decrease individuation
                # (though decay will handle most of it)
                pass
