"""Type definitions for the Socio-Psi agent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

# Type aliases for psyche components
PsycheComponent = Literal["shadow", "anima", "persona", "self", "default"]


class ThermalState(Enum):
    """Thermal state categories."""

    COOL = "cool"
    WARM = "warm"
    HOT = "hot"
    CRITICAL = "critical"


class NetworkState(Enum):
    """Network connection state."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LIMITED = "limited"


class LidState(Enum):
    """Lid open/closed state."""

    OPEN = "open"
    CLOSED = "closed"


class PowerState(Enum):
    """Power source state."""

    BATTERY = "battery"
    AC = "ac"
    CHARGING = "charging"


@dataclass
class SomaticState:
    """Current somatic (body) state of the machine."""

    battery_percent: int
    battery_health: int  # Percentage of original capacity
    battery_cycles: int
    power_state: PowerState
    cpu_percent: int
    gpu_percent: int
    thermal_state: ThermalState
    thermal_cpu: float  # Celsius
    thermal_gpu: float
    ram_percent: int
    storage_percent: int
    network_state: NetworkState
    lid_state: LidState
    fan_rpm: int
    uptime_seconds: int

    def to_tag(self) -> str:
        """Format as somatic tag for perception input."""
        return (
            f"[SOMATIC: battery={self.battery_percent}%, cpu={self.cpu_percent}%, "
            f"thermal={self.thermal_state.value}, ram={self.ram_percent}%, "
            f"network={self.network_state.value}, lid={self.lid_state.value}, "
            f"power={self.power_state.value}]"
        )


@dataclass
class Event:
    """An event that occurred since last heartbeat."""

    type: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of executing an action."""

    action_type: str
    success: bool
    result: Any = None
    error: str | None = None


@dataclass
class Action:
    """An action to be executed."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamSegment:
    """A segment of the psyche's inner dialogue."""

    component: PsycheComponent
    text: str


@dataclass
class PsycheResponse:
    """Parsed response from the psyche."""

    stream: list[StreamSegment]
    actions: list[Action]
    raw: str


@dataclass
class JournalEntry:
    """A journal entry."""

    timestamp: datetime
    entry: str
    mood: str | None = None
    somatic_snapshot: str | None = None


@dataclass
class NetworkDevice:
    """A device detected on the network."""

    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None


@dataclass
class BluetoothDevice:
    """A Bluetooth device detected nearby."""

    name: str
    address: str
    rssi: int  # Signal strength
    device_type: str | None = None
