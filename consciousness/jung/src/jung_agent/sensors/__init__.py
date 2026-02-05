"""Sensor modules for gathering machine state."""

from jung_agent.sensors.events import EventCollector
from jung_agent.sensors.external import (
    capture_audio,
    capture_camera,
    get_ambient_light,
    get_bluetooth_devices,
    get_fan_speed,
    get_location,
    get_motion,
    get_usb_connections,
)
from jung_agent.sensors.network import (
    ping_host,
    probe_host,
    scan_local_network,
    trace_route,
)
from jung_agent.sensors.somatic import gather_somatic

__all__ = [
    "gather_somatic",
    "EventCollector",
    "get_ambient_light",
    "get_bluetooth_devices",
    "get_location",
    "get_motion",
    "get_usb_connections",
    "capture_camera",
    "capture_audio",
    "get_fan_speed",
    "scan_local_network",
    "ping_host",
    "probe_host",
    "trace_route",
]
