"""Abstract base interfaces for platform hardware modules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sociopsi.types import BluetoothDevice, LidState, PowerState, ThermalState


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


class VolumeBackend(ABC):
    """Abstract volume control backend."""

    @abstractmethod
    def set_volume(self, level: int) -> dict:
        """Set system volume 0-100."""

    @abstractmethod
    def get_volume(self) -> int | None:
        """Get system volume 0-100, or None if unavailable."""


class NotificationBackend(ABC):
    """Abstract notification backend."""

    @abstractmethod
    def notify(self, title: str, message: str, duration: int = 30) -> dict:
        """Send a notification dialog."""

    @abstractmethod
    def display_message(self, text: str, duration: int = 5) -> dict:
        """Display a message on screen."""


class ClipboardBackend(ABC):
    """Abstract clipboard backend."""

    @abstractmethod
    def read_clipboard(self) -> str | None:
        """Read clipboard contents, or None if unavailable."""


class ScreenshotBackend(ABC):
    """Abstract screenshot backend."""

    @abstractmethod
    def take_screenshot(self, path: str) -> bool:
        """Capture screenshot to path. Returns True on success."""


class AppBackend(ABC):
    """Abstract application control backend."""

    @abstractmethod
    def open_app(self, name: str) -> dict:
        """Open an application by name."""

    @abstractmethod
    def close_app(self, name: str) -> dict:
        """Close an application by name."""


class NetworkControlBackend(ABC):
    """Abstract network control backend."""

    @abstractmethod
    def connect_wifi(self, ssid: str | None = None) -> dict:
        """Connect to WiFi (enable interface if no SSID)."""

    @abstractmethod
    def list_interfaces(self) -> list[dict]:
        """List network interfaces."""


@dataclass
class VoiceInfo:
    """TTS voice descriptor."""

    name: str
    identifier: str
    language: str
    quality: int  # Higher is better (0=default, 1=low, 2=enhanced, 3=premium)


class AudioBackend(ABC):
    """Abstract TTS and sound playback backend."""

    @abstractmethod
    def speak(self, text: str, voice: str | None = None, rate: int = 200) -> None:
        """Speak text aloud. Blocks until done.

        Args:
            text: Text to speak.
            voice: Voice name or identifier. None for system default.
            rate: Speech rate in words per minute.
        """

    @abstractmethod
    def play_sound(self, path: str) -> None:
        """Play an audio file. Blocks until done.

        Args:
            path: Path to audio file.
        """

    @abstractmethod
    def list_voices(self, language: str = "en") -> list[VoiceInfo]:
        """List available TTS voices.

        Args:
            language: Language prefix to filter by (e.g. "en").

        Returns:
            List of available voices, sorted by quality descending.
        """

    @abstractmethod
    def voice_available(self, name: str) -> bool:
        """Check if a named voice is available.

        Args:
            name: Voice display name (e.g. "Zoe (Premium)").
        """

    @abstractmethod
    def best_voice(self, language: str = "en") -> VoiceInfo | None:
        """Get the highest quality voice for a language.

        Args:
            language: Language prefix (e.g. "en").

        Returns:
            Best voice, or None if no voices available.
        """


@dataclass
class USBDevice:
    """USB device info."""

    name: str
    vendor: str
    serial: str | None = None


@dataclass
class ThunderboltDevice:
    """Thunderbolt device info."""

    name: str
    vendor: str
    device_id: str | None = None
    speed: str = "Unknown"


class DeviceBackend(ABC):
    """Abstract device enumeration backend."""

    @abstractmethod
    def list_usb(self) -> list[USBDevice]:
        """List connected USB devices."""

    @abstractmethod
    def list_bluetooth(self) -> list[BluetoothDevice]:
        """List connected Bluetooth devices."""

    @abstractmethod
    def list_thunderbolt(self) -> list[ThunderboltDevice]:
        """List connected Thunderbolt devices."""

    @abstractmethod
    def get_ambient_light(self) -> int | None:
        """Get ambient light sensor reading in lux, or None if unavailable."""

    @abstractmethod
    def get_motion(self) -> dict[str, str] | None:
        """Get motion sensor data, or None if unavailable."""
