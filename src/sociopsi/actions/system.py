"""System control actions: brightness, volume, power, sleep."""

import subprocess
from typing import Any

from sociopsi.platform import get_display_backend, get_power_backend


def set_brightness(level: int) -> dict[str, Any]:
    """Set display brightness (0-100)."""
    backend = get_display_backend()
    result = backend.set_brightness(level)
    level = max(0, min(100, level))
    if "error" not in result:
        result["description"] = _describe_brightness(level)
    return result


def _describe_brightness(level: int) -> str:
    """Describe brightness in experiential terms."""
    from sociopsi.describe import describe_brightness

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
    from sociopsi.describe import describe_volume

    return describe_volume(level)


def set_power_mode(mode: str) -> dict[str, Any]:
    """Set power mode: low, normal, or high."""
    backend = get_power_backend()
    return backend.set_power_mode(mode)


def sleep_system(duration: int | None = None) -> dict[str, Any]:
    """Put the system to sleep."""
    backend = get_power_backend()
    return backend.sleep(duration)


def wake_display(**kwargs: Any) -> dict[str, Any]:
    """Wake the display."""
    backend = get_power_backend()
    return backend.prevent_sleep(seconds=1)
