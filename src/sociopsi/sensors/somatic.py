"""Somatic (body state) sensors."""

import subprocess

import psutil

from sociopsi.types import (
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    ThermalState,
)


def get_battery_info() -> tuple[int, int, int, PowerState]:
    """Get battery percentage, health, cycles, and power state."""
    battery = psutil.sensors_battery()
    percent = int(battery.percent) if battery else 100

    # Determine power state
    if battery is None:
        power_state = PowerState.AC
    elif battery.power_plugged:
        power_state = PowerState.CHARGING if percent < 100 else PowerState.AC
    else:
        power_state = PowerState.BATTERY

    # Get battery health and cycles from system_profiler
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

    return percent, health, cycles, power_state


def get_thermal_state() -> tuple[ThermalState, float, float]:
    """Get thermal state and temperatures."""
    # Try to get temperatures via powermetrics or SMC
    cpu_temp = 50.0  # Default fallback
    gpu_temp = 45.0

    try:
        # Use osx-cpu-temp if available, or estimate from CPU usage
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
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, PermissionError):
        # Estimate from CPU usage as fallback
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_temp = 40 + (cpu_percent * 0.5)  # Rough estimate
        gpu_temp = cpu_temp * 0.9

    # Categorize thermal state
    max_temp = max(cpu_temp, gpu_temp)
    if max_temp >= 95:
        state = ThermalState.CRITICAL
    elif max_temp >= 80:
        state = ThermalState.HOT
    elif max_temp >= 60:
        state = ThermalState.WARM
    else:
        state = ThermalState.COOL

    return state, cpu_temp, gpu_temp


def get_network_state() -> NetworkState:
    """Get network connection state."""
    try:
        # Check for active network connections
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for iface, stat in stats.items():
            if stat.isup and iface not in ("lo", "lo0"):
                if iface in addrs:
                    for addr in addrs[iface]:
                        # Check for IPv4 address that's not localhost
                        if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                            return NetworkState.CONNECTED

        return NetworkState.DISCONNECTED
    except Exception:
        return NetworkState.LIMITED


def get_lid_state() -> LidState:
    """Get lid open/closed state."""
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
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return LidState.OPEN


def get_fan_speed() -> int:
    """Get fan RPM."""
    try:
        result = subprocess.run(
            ["sudo", "powermetrics", "-n", "1", "-i", "100", "--samplers", "smc"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in result.stdout.split("\n"):
            if "Fan" in line and "rpm" in line.lower():
                # Extract RPM value
                parts = line.split()
                for i, part in enumerate(parts):
                    if "rpm" in part.lower() and i > 0:
                        return int(parts[i - 1])
        return 0
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, PermissionError):
        return 0


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
