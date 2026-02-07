"""Environment actions: apps, network control."""

import subprocess
from typing import Any


def open_app(name: str) -> dict[str, Any]:
    """Open an application."""
    try:
        subprocess.run(
            ["open", "-a", name],
            capture_output=True,
            timeout=10,
        )
        return {
            "opened": True,
            "app": name,
            "description": f"brought {name} to life",
        }
    except Exception as e:
        return {"error": str(e), "description": f"could not open {name}"}


def close_app(name: str) -> dict[str, Any]:
    """Close an application."""
    try:
        script = f'''
        tell application "{name}"
            quit
        end tell
        '''
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=10,
        )
        return {
            "closed": True,
            "app": name,
            "description": f"ended {name}",
        }
    except Exception as e:
        return {"error": str(e), "description": f"could not close {name}"}


def connect_network(**kwargs: Any) -> dict[str, Any]:
    """Connect to WiFi."""
    try:
        # Get the WiFi interface name
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        wifi_device = None
        lines = result.stdout.split("\n")
        for i, line in enumerate(lines):
            if "Wi-Fi" in line:
                for j in range(i, min(i + 3, len(lines))):
                    if "Device:" in lines[j]:
                        wifi_device = lines[j].split(":")[-1].strip()
                        break
                break

        if wifi_device:
            subprocess.run(
                ["networksetup", "-setairportpower", wifi_device, "on"],
                capture_output=True,
                timeout=5,
            )
            return {
                "connected": True,
                "device": wifi_device,
                "description": "reaching out to the world",
            }
        else:
            return {"error": "WiFi device not found", "description": "cannot find way to connect"}

    except Exception as e:
        return {"error": str(e), "description": "could not connect"}
