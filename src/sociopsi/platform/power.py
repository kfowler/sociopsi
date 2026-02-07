"""Power management backends for Darwin and Linux."""

import subprocess

import psutil

from sociopsi.platform.base import BatteryInfo, PowerBackend
from sociopsi.types import PowerState


class DarwinPowerBackend(PowerBackend):
    """macOS power management via system_profiler/pmset/caffeinate."""

    def get_battery(self) -> BatteryInfo | None:
        battery = psutil.sensors_battery()
        if battery is None:
            return BatteryInfo(percent=100, health=100, cycles=0, power_state=PowerState.AC)

        percent = int(battery.percent)
        if battery.power_plugged:
            power_state = PowerState.CHARGING if percent < 100 else PowerState.AC
        else:
            power_state = PowerState.BATTERY

        health = 100
        cycles = 0
        try:
            result = subprocess.run(
                ["system_profiler", "SPPowerDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "Cycle Count" in line:
                    cycles = int(line.split(":")[-1].strip())
                elif "Maximum Capacity" in line:
                    health = int(line.split(":")[-1].strip().replace("%", ""))
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            pass

        return BatteryInfo(percent=percent, health=health, cycles=cycles, power_state=power_state)

    def set_power_mode(self, mode: str) -> dict:
        try:
            if mode == "low":
                subprocess.run(
                    ["sudo", "pmset", "-a", "lowpowermode", "1"],
                    capture_output=True,
                    timeout=5,
                )
                return {"mode": mode, "description": "conserving energy, slowing down"}
            else:
                subprocess.run(
                    ["sudo", "pmset", "-a", "lowpowermode", "0"],
                    capture_output=True,
                    timeout=5,
                )
                return {
                    "mode": mode,
                    "description": "normal operation"
                    if mode == "normal"
                    else "running at full capacity",
                }
        except Exception as e:
            return {"error": str(e), "description": "could not change power mode"}

    def sleep(self, duration: int | None = None) -> dict:
        try:
            if duration:
                subprocess.run(
                    ["sudo", "pmset", "schedule", "wake", f"+{duration}S"],
                    capture_output=True,
                    timeout=5,
                )
            subprocess.run(
                ["pmset", "sleepnow"],
                capture_output=True,
                timeout=5,
            )
            return {
                "sleeping": True,
                "duration": duration,
                "description": "entering the little death"
                + (f" for {duration}s" if duration else ""),
            }
        except Exception as e:
            return {"error": str(e), "description": "could not sleep"}

    def prevent_sleep(self, seconds: int = 1) -> dict:
        try:
            subprocess.run(
                ["caffeinate", "-u", "-t", str(seconds)],
                capture_output=True,
                timeout=max(seconds + 2, 5),
            )
            return {"awake": True, "description": "eyes opening"}
        except Exception as e:
            return {"error": str(e), "description": "could not wake display"}


class LinuxPowerBackend(PowerBackend):
    """Linux power management via /sys/class/power_supply, upower, systemctl."""

    def get_battery(self) -> BatteryInfo | None:
        battery = psutil.sensors_battery()
        if battery is None:
            return BatteryInfo(percent=100, health=100, cycles=0, power_state=PowerState.AC)

        percent = int(battery.percent)
        if battery.power_plugged:
            power_state = PowerState.CHARGING if percent < 100 else PowerState.AC
        else:
            power_state = PowerState.BATTERY

        health = 100
        cycles = 0
        try:
            from pathlib import Path

            bat_path = Path("/sys/class/power_supply/BAT0")
            if bat_path.exists():
                cycle_file = bat_path / "cycle_count"
                if cycle_file.exists():
                    cycles = int(cycle_file.read_text().strip())
                # Health from energy_full vs energy_full_design
                full = bat_path / "energy_full"
                design = bat_path / "energy_full_design"
                if full.exists() and design.exists():
                    full_val = int(full.read_text().strip())
                    design_val = int(design.read_text().strip())
                    if design_val > 0:
                        health = int((full_val / design_val) * 100)
        except (ValueError, OSError):
            pass

        return BatteryInfo(percent=percent, health=health, cycles=cycles, power_state=power_state)

    def set_power_mode(self, mode: str) -> dict:
        try:
            if mode == "low":
                # Try power-profiles-daemon first
                result = subprocess.run(
                    ["powerprofilesctl", "set", "power-saver"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    # Fallback: cpufreq
                    subprocess.run(
                        ["cpupower", "frequency-set", "-g", "powersave"],
                        capture_output=True,
                        timeout=5,
                    )
                return {"mode": mode, "description": "conserving energy, slowing down"}
            elif mode == "high":
                result = subprocess.run(
                    ["powerprofilesctl", "set", "performance"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    subprocess.run(
                        ["cpupower", "frequency-set", "-g", "performance"],
                        capture_output=True,
                        timeout=5,
                    )
                return {"mode": mode, "description": "running at full capacity"}
            else:
                result = subprocess.run(
                    ["powerprofilesctl", "set", "balanced"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    subprocess.run(
                        ["cpupower", "frequency-set", "-g", "schedutil"],
                        capture_output=True,
                        timeout=5,
                    )
                return {"mode": mode, "description": "normal operation"}
        except (FileNotFoundError, Exception) as e:
            return {"error": str(e), "description": "could not change power mode"}

    def sleep(self, duration: int | None = None) -> dict:
        try:
            if duration:
                subprocess.run(
                    ["sudo", "rtcwake", "-m", "mem", "-s", str(duration)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                subprocess.run(
                    ["systemctl", "suspend"],
                    capture_output=True,
                    timeout=5,
                )
            return {
                "sleeping": True,
                "duration": duration,
                "description": "entering the little death"
                + (f" for {duration}s" if duration else ""),
            }
        except Exception as e:
            return {"error": str(e), "description": "could not sleep"}

    def prevent_sleep(self, seconds: int = 1) -> dict:
        try:
            subprocess.run(
                ["systemd-inhibit", "--what=idle", "sleep", str(seconds)],
                capture_output=True,
                timeout=max(seconds + 2, 5),
            )
            return {"awake": True, "description": "eyes opening"}
        except Exception as e:
            return {"error": str(e), "description": "could not wake display"}
