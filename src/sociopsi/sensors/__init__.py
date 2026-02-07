"""Sensor modules for gathering machine state."""

from sociopsi.sensors.events import EventCollector
from sociopsi.sensors.external import (
    capture_audio,
    capture_camera,
    get_ambient_light,
    get_bluetooth_devices,
    get_fan_speed,
    get_location,
    get_motion,
    get_usb_connections,
)
from sociopsi.sensors.network import (
    ping_host,
    probe_host,
    scan_local_network,
    trace_route,
)
from sociopsi.sensors.somatic import SomaticPoller, gather_somatic

__all__ = [
    "gather_somatic",
    "SomaticPoller",
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
