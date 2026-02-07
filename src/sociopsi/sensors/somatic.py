"""Somatic (body state) sensors."""

import psutil

from sociopsi.platform import get_display_backend, get_power_backend, get_thermal_backend
from sociopsi.types import (
    NetworkState,
    SomaticState,
)


def get_battery_info():
    """Get battery info via platform backend."""
    backend = get_power_backend()
    info = backend.get_battery()
    if info is None:
        from sociopsi.types import PowerState

        return 100, 100, 0, PowerState.AC
    return info.percent, info.health, info.cycles, info.power_state


def get_thermal_state():
    """Get thermal state via platform backend."""
    backend = get_thermal_backend()
    info = backend.get_thermals()
    if info is None:
        from sociopsi.types import ThermalState

        return ThermalState.COOL, 50.0, 45.0
    return info.state, info.cpu_temp, info.gpu_temp


def get_network_state() -> NetworkState:
    """Get network connection state."""
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for iface, stat in stats.items():
            if stat.isup and iface not in ("lo", "lo0"):
                if iface in addrs:
                    for addr in addrs[iface]:
                        if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                            return NetworkState.CONNECTED

        return NetworkState.DISCONNECTED
    except Exception:
        return NetworkState.LIMITED


def get_lid_state():
    """Get lid state via platform backend."""
    backend = get_display_backend()
    return backend.get_lid_state()


def get_fan_speed() -> int:
    """Get fan RPM via platform backend."""
    backend = get_thermal_backend()
    rpm = backend.get_fan_speed()
    return rpm if rpm is not None else 0


def get_uptime() -> int:
    """Get system uptime in seconds."""
    import time

    boot_time = psutil.boot_time()
    return int(time.time() - boot_time)


def gather_somatic() -> SomaticState:
    """Gather complete somatic state."""
    battery_percent, battery_health, battery_cycles, power_state = get_battery_info()
    thermal_state, thermal_cpu, thermal_gpu = get_thermal_state()

    cpu_percent = int(psutil.cpu_percent(interval=0.1))
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Estimate GPU usage (M2 doesn't expose this easily)
    gpu_percent = min(cpu_percent + 10, 100)  # Rough estimate

    return SomaticState(
        battery_percent=battery_percent,
        battery_health=battery_health,
        battery_cycles=battery_cycles,
        power_state=power_state,
        cpu_percent=cpu_percent,
        gpu_percent=gpu_percent,
        thermal_state=thermal_state,
        thermal_cpu=thermal_cpu,
        thermal_gpu=thermal_gpu,
        ram_percent=int(ram.percent),
        storage_percent=int(disk.percent),
        network_state=get_network_state(),
        lid_state=get_lid_state(),
        fan_rpm=get_fan_speed(),
        uptime_seconds=get_uptime(),
    )
