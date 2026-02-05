"""System control actions: brightness, volume, power, sleep."""

import subprocess
from typing import Any


def set_brightness(level: int) -> dict[str, Any]:
    """Set display brightness (0-100)."""
    level = max(0, min(100, level))
    normalized = level / 100.0

    try:
        # Use brightness command if available (brew install brightness)
        subprocess.run(
            ["brightness", str(normalized)],
            capture_output=True,
            timeout=5,
        )
        return {"set_to": level, "description": _describe_brightness(level)}
    except FileNotFoundError:
        # Fallback to AppleScript
        try:
            script = f'tell application "System Events" to set value of slider 1 of group 1 of window "Control Center" of process "ControlCenter" to {level}'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5,
            )
            return {"set_to": level, "description": _describe_brightness(level)}
        except Exception as e:
            return {"error": str(e), "description": "could not adjust brightness"}


def _describe_brightness(level: int) -> str:
    """Describe brightness in experiential terms."""
    from jung_agent.describe import describe_brightness

    return describe_brightness(level)


def set_volume(level: int) -> dict[str, Any]:
    """Set system volume (0-100)."""
    level = max(0, min(100, level))

    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            capture_output=True,
            timeout=5,
        )
        return {"set_to": level, "description": _describe_volume(level)}
    except Exception as e:
        return {"error": str(e), "description": "could not adjust volume"}


def _describe_volume(level: int) -> str:
    """Describe volume in experiential terms."""
    from jung_agent.describe import describe_volume

    return describe_volume(level)


def set_power_mode(mode: str) -> dict[str, Any]:
    """Set power mode: low, normal, or high."""
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


def sleep_system(duration: int | None = None) -> dict[str, Any]:
    """Put the system to sleep."""
    try:
        if duration:
            # Schedule wake before sleep
            subprocess.run(
                [
                    "sudo",
                    "pmset",
                    "schedule",
                    "wake",
                    f"+{duration}S",
                ],
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
            "description": "entering the little death" + (f" for {duration}s" if duration else ""),
        }
    except Exception as e:
        return {"error": str(e), "description": "could not sleep"}


def wake_display(**kwargs: Any) -> dict[str, Any]:
    """Wake the display."""
    try:
        subprocess.run(
            ["caffeinate", "-u", "-t", "1"],
            capture_output=True,
            timeout=5,
        )
        return {"awake": True, "description": "eyes opening"}
    except Exception as e:
        return {"error": str(e), "description": "could not wake display"}
