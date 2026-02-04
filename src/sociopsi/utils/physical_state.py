"""Physical state monitoring (battery, CPU)."""

import psutil
from typing import Optional


class PhysicalState:
    """Monitor physical system state."""

    def get_battery_percent(self) -> Optional[float]:
        """Get battery percentage.

        Returns:
            Battery percentage (0-100) or None if no battery
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return battery.percent

    def is_plugged_in(self) -> Optional[bool]:
        """Check if power is plugged in.

        Returns:
            True if plugged in, False if on battery, None if no battery
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return battery.power_plugged

    def get_cpu_percent(self, interval: float = 0.1) -> float:
        """Get current CPU usage percentage.

        Args:
            interval: Measurement interval in seconds

        Returns:
            CPU usage percentage (0-100)
        """
        return psutil.cpu_percent(interval=interval)

    def get_state(self) -> dict:
        """Get complete physical state.

        Returns:
            Dictionary with battery_percent, cpu_percent, is_plugged_in
        """
        return {
            "battery_percent": self.get_battery_percent(),
            "cpu_percent": self.get_cpu_percent(),
            "is_plugged_in": self.is_plugged_in(),
        }
