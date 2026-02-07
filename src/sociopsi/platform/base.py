"""Abstract base interfaces for platform hardware modules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sociopsi.types import LidState, PowerState, ThermalState


@dataclass
class BatteryInfo:
    """Battery state snapshot."""

    percent: int
    health: int  # Percentage of original capacity
    cycles: int
    power_state: PowerState


@dataclass
class ThermalInfo:
    """Thermal state snapshot."""

    state: ThermalState
    cpu_temp: float  # Celsius
    gpu_temp: float  # Celsius


@dataclass
class DisplayInfo:
    """Display device info."""

    name: str
    resolution: str
    connection_type: str
    is_main: bool
    mirror: str


class SensorUnavailable(Exception):
    """Raised when a sensor is not available on this platform."""


class PowerBackend(ABC):
    """Abstract power management backend."""

    @abstractmethod
    def get_battery(self) -> BatteryInfo | None:
        """Get battery info, or None if no battery."""

    @abstractmethod
    def set_power_mode(self, mode: str) -> dict:
        """Set power mode: low, normal, or high."""

    @abstractmethod
    def sleep(self, duration: int | None = None) -> dict:
        """Put the system to sleep."""

    @abstractmethod
    def prevent_sleep(self, seconds: int = 1) -> dict:
        """Prevent sleep / wake the display."""


class ThermalBackend(ABC):
    """Abstract thermal monitoring backend."""

    @abstractmethod
    def get_thermals(self) -> ThermalInfo | None:
        """Get thermal info, or None if unavailable."""

    @abstractmethod
    def get_fan_speed(self) -> int | None:
        """Get fan RPM, or None if unavailable."""


class DisplayBackend(ABC):
    """Abstract display management backend."""

    @abstractmethod
    def get_brightness(self) -> int | None:
        """Get display brightness 0-100, or None if unavailable."""

    @abstractmethod
    def set_brightness(self, level: int) -> dict:
        """Set display brightness 0-100."""

    @abstractmethod
    def get_lid_state(self) -> LidState:
        """Get lid open/closed state."""

    @abstractmethod
    def list_displays(self) -> list[DisplayInfo]:
        """List connected displays."""
