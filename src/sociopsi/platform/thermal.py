"""Thermal monitoring backends for Darwin and Linux."""

import subprocess

import psutil

from sociopsi.platform.base import ThermalBackend, ThermalInfo
from sociopsi.types import ThermalState


def _classify_thermal(cpu_temp: float, gpu_temp: float) -> ThermalState:
    """Classify thermal state from temperatures."""
    max_temp = max(cpu_temp, gpu_temp)
    if max_temp >= 95:
        return ThermalState.CRITICAL
    elif max_temp >= 80:
        return ThermalState.HOT
    elif max_temp >= 60:
        return ThermalState.WARM
    else:
        return ThermalState.COOL


class DarwinThermalBackend(ThermalBackend):
    """macOS thermal monitoring via powermetrics."""

    def get_thermals(self) -> ThermalInfo | None:
        cpu_temp = 50.0
        gpu_temp = 45.0

        try:
            result = subprocess.run(
                ["sudo", "powermetrics", "-n", "1", "-i", "100", "--samplers", "smc"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in result.stdout.split("\n"):
                if "CPU die temperature" in line:
                    cpu_temp = float(line.split(":")[-1].strip().replace(" C", ""))
                elif "GPU die temperature" in line:
                    gpu_temp = float(line.split(":")[-1].strip().replace(" C", ""))
        except subprocess.TimeoutExpired, ValueError, FileNotFoundError, PermissionError:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_temp = 40 + (cpu_percent * 0.5)
            gpu_temp = cpu_temp * 0.9

        return ThermalInfo(
            state=_classify_thermal(cpu_temp, gpu_temp),
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
        )

    def get_fan_speed(self) -> int | None:
        try:
            result = subprocess.run(
                ["sudo", "powermetrics", "-n", "1", "-i", "100", "--samplers", "smc"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in result.stdout.split("\n"):
                if "Fan" in line and "rpm" in line.lower():
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "rpm" in part.lower() and i > 0:
                            return int(parts[i - 1])
            return 0
        except subprocess.TimeoutExpired, ValueError, FileNotFoundError, PermissionError:
            return 0


class LinuxThermalBackend(ThermalBackend):
    """Linux thermal monitoring via /sys/class/thermal and hwmon."""

    def get_thermals(self) -> ThermalInfo | None:
        cpu_temp = 50.0
        gpu_temp = 45.0

        try:
            from pathlib import Path

            # Try thermal zones first
            thermal_base = Path("/sys/class/thermal")
            zones = sorted(thermal_base.glob("thermal_zone*"))
            for zone in zones:
                temp_file = zone / "temp"
                type_file = zone / "type"
                if temp_file.exists():
                    temp = int(temp_file.read_text().strip()) / 1000.0
                    zone_type = ""
                    if type_file.exists():
                        zone_type = type_file.read_text().strip().lower()
                    if "cpu" in zone_type or "x86_pkg" in zone_type or "coretemp" in zone_type:
                        cpu_temp = temp
                    elif "gpu" in zone_type:
                        gpu_temp = temp
                    elif cpu_temp == 50.0:
                        # Use first available as CPU temp fallback
                        cpu_temp = temp
        except ValueError, OSError:
            pass

        # Fallback: try lm-sensors via psutil
        if cpu_temp == 50.0:
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current > 0:
                                if "core" in name.lower() or "cpu" in name.lower():
                                    cpu_temp = entry.current
                                elif "gpu" in name.lower():
                                    gpu_temp = entry.current
            except AttributeError, OSError:
                pass

        return ThermalInfo(
            state=_classify_thermal(cpu_temp, gpu_temp),
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
        )

    def get_fan_speed(self) -> int | None:
        try:
            from pathlib import Path

            hwmon_base = Path("/sys/class/hwmon")
            for hwmon in hwmon_base.iterdir():
                for fan_input in hwmon.glob("fan*_input"):
                    rpm = int(fan_input.read_text().strip())
                    if rpm > 0:
                        return rpm
        except ValueError, OSError:
            pass

        # Fallback: psutil fans
        try:
            fans = psutil.sensors_fans()
            if fans:
                for entries in fans.values():
                    for entry in entries:
                        if entry.current > 0:
                            return int(entry.current)
        except AttributeError, OSError:
            pass

        return 0
