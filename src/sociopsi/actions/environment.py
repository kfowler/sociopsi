"""Environment actions: apps, network control."""

from typing import Any

from sociopsi.platform import get_app_backend, get_network_backend


def open_app(name: str) -> dict[str, Any]:
    """Open an application."""
    backend = get_app_backend()
    result = backend.open_app(name)
    if "error" not in result:
        result["description"] = f"brought {name} to life"
    else:
        result["description"] = f"could not open {name}"
    return result


def close_app(name: str) -> dict[str, Any]:
    """Close an application."""
    backend = get_app_backend()
    result = backend.close_app(name)
    if "error" not in result:
        result["description"] = f"ended {name}"
    else:
        result["description"] = f"could not close {name}"
    return result


def connect_network(**kwargs: Any) -> dict[str, Any]:
    """Connect to WiFi."""
    backend = get_network_backend()
    result = backend.connect_wifi()
    if "error" not in result:
        result["description"] = "reaching out to the world"
    else:
        result["description"] = "could not connect"
    return result
