"""Display management backends for Darwin and Linux."""

import json
import logging
import subprocess

from sociopsi.platform.base import DisplayBackend, DisplayInfo
from sociopsi.types import LidState

logger = logging.getLogger(__name__)


class DarwinDisplayBackend(DisplayBackend):
    """macOS display management via brightness CLI, ioreg, system_profiler."""

    def get_brightness(self) -> int | None:
        try:
            result = subprocess.run(
                ["brightness", "-l"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "brightness" in line.lower():
                    # Parse "display 0: brightness X.XXXX"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "brightness" and i + 1 < len(parts):
                            return int(float(parts[i + 1]) * 100)
            return None
        except FileNotFoundError, subprocess.TimeoutExpired, ValueError:
            return None

    def set_brightness(self, level: int) -> dict:
        level = max(0, min(100, level))
        normalized = level / 100.0

        try:
            subprocess.run(
                ["brightness", str(normalized)],
                capture_output=True,
                timeout=5,
            )
            return {"set_to": level}
        except FileNotFoundError:
            try:
                script = (
                    f'tell application "System Events" to set value of slider 1 '
                    f'of group 1 of window "Control Center" of process "ControlCenter" to {level}'
                )
                subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    timeout=5,
                )
                return {"set_to": level}
            except Exception as e:
                return {"error": str(e), "description": "could not adjust brightness"}

    def get_lid_state(self) -> LidState:
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-k", "AppleClamshellState", "-d", "4"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if '"AppleClamshellState" = Yes' in result.stdout:
                return LidState.CLOSED
            return LidState.OPEN
        except subprocess.TimeoutExpired, FileNotFoundError:
            return LidState.OPEN

    def list_displays(self) -> list[DisplayInfo]:
        displays: list[DisplayInfo] = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)
            display_data = data.get("SPDisplaysDataType", [])

            for gpu in display_data:
                for display in gpu.get("spdisplays_ndrvs", []):
                    displays.append(
                        DisplayInfo(
                            name=display.get("_name", "Unknown"),
                            resolution=display.get("_spdisplays_resolution", "Unknown"),
                            connection_type=display.get("spdisplays_connection_type", "Unknown"),
                            is_main=display.get("spdisplays_main", "No") == "Yes",
                            mirror=display.get("spdisplays_mirror", "Off"),
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Display info timed out")
        except ValueError as e:
            logger.warning(f"Display info parse error: {e}")
        except FileNotFoundError:
            logger.warning("system_profiler not found")
        return displays


class LinuxDisplayBackend(DisplayBackend):
    """Linux display management via xrandr, ddcutil, /proc/acpi."""

    def get_brightness(self) -> int | None:
        # Try backlight sysfs first
        try:
            from pathlib import Path

            backlight_base = Path("/sys/class/backlight")
            for bl in backlight_base.iterdir():
                brightness = int((bl / "brightness").read_text().strip())
                max_brightness = int((bl / "max_brightness").read_text().strip())
                if max_brightness > 0:
                    return int((brightness / max_brightness) * 100)
        except ValueError, OSError:
            pass

        # Try ddcutil for external monitors
        try:
            result = subprocess.run(
                ["ddcutil", "getvcp", "10"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "current value" in result.stdout.lower():
                for part in result.stdout.split(","):
                    if "current value" in part.lower():
                        return int(part.split("=")[-1].strip())
        except FileNotFoundError, subprocess.TimeoutExpired, ValueError:
            pass

        return None

    def set_brightness(self, level: int) -> dict:
        level = max(0, min(100, level))

        # Try backlight sysfs
        try:
            from pathlib import Path

            backlight_base = Path("/sys/class/backlight")
            for bl in backlight_base.iterdir():
                max_brightness = int((bl / "max_brightness").read_text().strip())
                target = int((level / 100) * max_brightness)
                (bl / "brightness").write_text(str(target))
                return {"set_to": level}
        except ValueError, OSError:
            pass

        # Try xrandr
        try:
            normalized = level / 100.0
            result = subprocess.run(
                ["xrandr", "--output", "eDP-1", "--brightness", str(normalized)],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return {"set_to": level}
        except FileNotFoundError, subprocess.TimeoutExpired:
            pass

        return {
            "error": "no brightness control available",
            "description": "could not adjust brightness",
        }

    def get_lid_state(self) -> LidState:
        try:
            from pathlib import Path

            lid_path = Path("/proc/acpi/button/lid/LID0/state")
            if lid_path.exists():
                state = lid_path.read_text().strip().lower()
                if "closed" in state:
                    return LidState.CLOSED
                return LidState.OPEN
        except OSError:
            pass
        return LidState.OPEN

    def list_displays(self) -> list[DisplayInfo]:
        displays: list[DisplayInfo] = []
        try:
            result = subprocess.run(
                ["xrandr", "--listmonitors"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                parts = line.strip().split()
                if len(parts) >= 4:
                    is_main = parts[0].startswith("*") or "+*" in line
                    name = parts[-1] if parts else "Unknown"
                    # Extract resolution from the geometry string
                    resolution = parts[2] if len(parts) > 2 else "Unknown"
                    displays.append(
                        DisplayInfo(
                            name=name,
                            resolution=resolution,
                            connection_type="xrandr",
                            is_main=is_main,
                            mirror="Off",
                        )
                    )
        except FileNotFoundError, subprocess.TimeoutExpired:
            logger.warning("xrandr not available")
        return displays
