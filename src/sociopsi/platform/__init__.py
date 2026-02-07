"""Platform abstraction layer for hardware access.

Detects the current platform and provides the appropriate backends
for power, thermal, and display management.
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


__all__ = [
    "BatteryInfo",
    "DisplayBackend",
    "DisplayInfo",
    "PowerBackend",
    "SensorUnavailable",
    "ThermalBackend",
    "ThermalInfo",
    "get_display_backend",
    "get_power_backend",
    "get_thermal_backend",
]
