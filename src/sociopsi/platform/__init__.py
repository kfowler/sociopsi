"""Platform abstraction layer for hardware access.

Detects the current platform and provides the appropriate backends
for power, thermal, display, and speech recognition.
"""

import sys

from sociopsi.platform.base import (
    BatteryInfo,
    DisplayBackend,
    DisplayInfo,
    PowerBackend,
    SensorUnavailable,
    ThermalBackend,
    ThermalInfo,
)
from sociopsi.platform.speech import SpeechBackend


def _detect_platform() -> str:
    """Detect the current platform."""
    if sys.platform == "darwin":
        return "darwin"
    elif sys.platform.startswith("linux"):
        return "linux"
    else:
        return sys.platform


def get_power_backend() -> PowerBackend:
    """Get the power management backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.power import DarwinPowerBackend

        return DarwinPowerBackend()
    elif platform == "linux":
        from sociopsi.platform.power import LinuxPowerBackend

        return LinuxPowerBackend()
    else:
        raise SensorUnavailable(f"No power backend for platform: {platform}")


def get_thermal_backend() -> ThermalBackend:
    """Get the thermal monitoring backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.thermal import DarwinThermalBackend

        return DarwinThermalBackend()
    elif platform == "linux":
        from sociopsi.platform.thermal import LinuxThermalBackend

        return LinuxThermalBackend()
    else:
        raise SensorUnavailable(f"No thermal backend for platform: {platform}")


def get_display_backend() -> DisplayBackend:
    """Get the display management backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.display import DarwinDisplayBackend

        return DarwinDisplayBackend()
    elif platform == "linux":
        from sociopsi.platform.display import LinuxDisplayBackend

        return LinuxDisplayBackend()
    else:
        raise SensorUnavailable(f"No display backend for platform: {platform}")


def get_speech_backend(locale: str = "en-US", on_device: bool = True) -> SpeechBackend:
    """Get the speech recognition backend for the current platform.

    Args:
        locale: BCP-47 locale for speech recognition.
        on_device: Force on-device recognition (Darwin only).
    """
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.speech import DarwinSpeechBackend

        return DarwinSpeechBackend(locale=locale, on_device=on_device)
    elif platform == "linux":
        from sociopsi.platform.speech import LinuxSpeechBackend

        return LinuxSpeechBackend()
    else:
        raise SensorUnavailable(f"No speech backend for platform: {platform}")


__all__ = [
    "BatteryInfo",
    "DisplayBackend",
    "DisplayInfo",
    "PowerBackend",
    "SensorUnavailable",
    "SpeechBackend",
    "ThermalBackend",
    "ThermalInfo",
    "get_display_backend",
    "get_power_backend",
    "get_speech_backend",
    "get_thermal_backend",
]
