"""Somatic (body state) sensors with tiered polling.

Three independent polling tiers avoid blocking the agent cycle:
  Fast   (1s) : CPU load, RAM usage, network connectivity — via psutil
  Medium (10s): Battery level/health, lid state, power state — via platform
  Slow   (30s): Thermal (CPU/GPU temp), fan speed — via platform (subprocess)

All readings are stored in thread-safe shared state. The agent reads the latest
snapshot via SomaticPoller.snapshot() without ever waiting for a sensor read.
"""

import copy
import threading
import time
from collections.abc import Callable
from dataclasses import replace

import psutil

from sociopsi.platform import get_display_backend, get_power_backend, get_thermal_backend
from sociopsi.types import (
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    ThermalState,
)

# Event callback: (event_type, description, data_dict)
SomaticEventCallback = Callable[[str, str, dict], None]

# Default tier intervals (seconds)
FAST_INTERVAL = 1.0
MEDIUM_INTERVAL = 10.0
SLOW_INTERVAL = 30.0


# ---------------------------------------------------------------------------
# Raw sensor helpers (unchanged from previous monolithic gather)
# ---------------------------------------------------------------------------

def get_battery_info() -> tuple[int, int, int, PowerState]:
    """Get battery info via platform backend."""
    backend = get_power_backend()
    info = backend.get_battery()
    if info is None:
        return 100, 100, 0, PowerState.AC
    return info.percent, info.health, info.cycles, info.power_state


def get_thermal_state() -> tuple[ThermalState, float, float]:
    """Get thermal state via platform backend."""
    backend = get_thermal_backend()
    info = backend.get_thermals()
    if info is None:
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


def get_lid_state() -> LidState:
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
    boot_time = psutil.boot_time()
    return int(time.time() - boot_time)


# ---------------------------------------------------------------------------
# Backwards-compat: synchronous gather (used by one-shot callers)
# ---------------------------------------------------------------------------

def gather_somatic() -> SomaticState:
    """Gather complete somatic state synchronously.

    Prefer SomaticPoller.snapshot() in the agent loop.
    """
    battery_percent, battery_health, battery_cycles, power_state = get_battery_info()
    thermal_state, thermal_cpu, thermal_gpu = get_thermal_state()

    cpu_percent = int(psutil.cpu_percent(interval=0.1))
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    gpu_percent = min(cpu_percent + 10, 100)

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


# ---------------------------------------------------------------------------
# SomaticPoller: tiered threaded polling with shared state
# ---------------------------------------------------------------------------

def _default_state() -> SomaticState:
    """Return a safe default SomaticState for initialisation."""
    return SomaticState(
        battery_percent=100,
        battery_health=100,
        battery_cycles=0,
        power_state=PowerState.AC,
        cpu_percent=0,
        gpu_percent=0,
        thermal_state=ThermalState.COOL,
        thermal_cpu=50.0,
        thermal_gpu=45.0,
        ram_percent=0,
        storage_percent=0,
        network_state=NetworkState.DISCONNECTED,
        lid_state=LidState.OPEN,
        fan_rpm=0,
        uptime_seconds=0,
    )


class SomaticPoller:
    """Thread-safe tiered sensor polling.

    Three daemon threads poll sensors at independent intervals and update a
    shared SomaticState under an RLock. The agent reads the latest snapshot
    via .snapshot() which never blocks on a sensor read.

    An optional event_callback receives immediate threshold-crossing events
    (thermal critical, battery low, etc.) so the EventCollector can fire
    them without waiting for the next agent cycle.
    """

    def __init__(
        self,
        *,
        fast_interval: float = FAST_INTERVAL,
        medium_interval: float = MEDIUM_INTERVAL,
        slow_interval: float = SLOW_INTERVAL,
        event_callback: SomaticEventCallback | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._state = _default_state()
        self._running = False
        self._threads: list[threading.Thread] = []
        self._event_callback = event_callback

        self._fast_interval = fast_interval
        self._medium_interval = medium_interval
        self._slow_interval = slow_interval

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the three polling daemon threads.

        Also runs one synchronous pass so snapshot() returns real data
        immediately after start().
        """
        if self._running:
            return
        self._running = True

        # Seed state synchronously so first snapshot() is real
        self._poll_fast_once()
        self._poll_medium_once()
        self._poll_slow_once()

        for target, name in (
            (self._poll_fast_loop, "somatic-fast"),
            (self._poll_medium_loop, "somatic-medium"),
            (self._poll_slow_loop, "somatic-slow"),
        ):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        """Stop all polling threads."""
        self._running = False
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads.clear()

    # -- public API ----------------------------------------------------------

    def snapshot(self) -> SomaticState:
        """Return a copy of the latest somatic state (never blocks on I/O)."""
        with self._lock:
            return copy.copy(self._state)

    # -- polling loops -------------------------------------------------------

    def _poll_fast_loop(self) -> None:
        """Fast tier loop: CPU, RAM, network, uptime (1s)."""
        while self._running:
            time.sleep(self._fast_interval)
            if not self._running:
                break
            self._poll_fast_once()

    def _poll_medium_loop(self) -> None:
        """Medium tier loop: battery, lid, power (10s)."""
        while self._running:
            time.sleep(self._medium_interval)
            if not self._running:
                break
            self._poll_medium_once()

    def _poll_slow_loop(self) -> None:
        """Slow tier loop: thermal, fan (30s)."""
        while self._running:
            time.sleep(self._slow_interval)
            if not self._running:
                break
            self._poll_slow_once()

    # -- single-pass polling -------------------------------------------------

    def _poll_fast_once(self) -> None:
        """Poll fast-tier sensors and update shared state."""
        try:
            cpu = int(psutil.cpu_percent(interval=0))
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            network = get_network_state()
            uptime = get_uptime()
            gpu = min(cpu + 10, 100)
        except Exception:
            return

        with self._lock:
            old = self._state
            self._state = replace(
                old,
                cpu_percent=cpu,
                gpu_percent=gpu,
                ram_percent=int(ram.percent),
                storage_percent=int(disk.percent),
                network_state=network,
                uptime_seconds=uptime,
            )
            self._check_fast_events(old, self._state)

    def _poll_medium_once(self) -> None:
        """Poll medium-tier sensors and update shared state."""
        try:
            battery_percent, battery_health, battery_cycles, power_state = get_battery_info()
            lid = get_lid_state()
        except Exception:
            return

        with self._lock:
            old = self._state
            self._state = replace(
                old,
                battery_percent=battery_percent,
                battery_health=battery_health,
                battery_cycles=battery_cycles,
                power_state=power_state,
                lid_state=lid,
            )
            self._check_medium_events(old, self._state)

    def _poll_slow_once(self) -> None:
        """Poll slow-tier sensors and update shared state."""
        try:
            thermal_state, thermal_cpu, thermal_gpu = get_thermal_state()
            fan = get_fan_speed()
        except Exception:
            return

        with self._lock:
            old = self._state
            self._state = replace(
                old,
                thermal_state=thermal_state,
                thermal_cpu=thermal_cpu,
                thermal_gpu=thermal_gpu,
                fan_rpm=fan,
            )
            self._check_slow_events(old, self._state)

    # -- threshold event detection -------------------------------------------

    def _fire(self, event_type: str, description: str, **data: object) -> None:
        """Fire an event via the callback if registered."""
        if self._event_callback is not None:
            self._event_callback(event_type, description, dict(data))

    def _check_fast_events(self, old: SomaticState, new: SomaticState) -> None:
        if old.network_state != new.network_state:
            if new.network_state == NetworkState.CONNECTED:
                self._fire("network_connected", "Connected to the world")
            elif new.network_state == NetworkState.DISCONNECTED:
                self._fire("network_disconnected", "Isolated")

    def _check_medium_events(self, old: SomaticState, new: SomaticState) -> None:
        if old.power_state != new.power_state:
            if new.power_state == PowerState.CHARGING:
                self._fire("power_connected", "Being fed")
            elif new.power_state == PowerState.BATTERY:
                self._fire("power_disconnected", "Unplugged")

        if old.lid_state != new.lid_state:
            if new.lid_state == LidState.OPEN:
                self._fire("lid_opened", "Eyes opening")
            else:
                self._fire("lid_closed", "Eyes closing")

        if new.battery_percent <= 10 and old.battery_percent > 10:
            self._fire(
                "battery_critical",
                f"Battery critical: {new.battery_percent}%",
                level=new.battery_percent,
            )

        if new.battery_percent == 100 and old.battery_percent < 100:
            self._fire("battery_full", "Fully charged")

    def _check_slow_events(self, old: SomaticState, new: SomaticState) -> None:
        if old.thermal_state != new.thermal_state:
            if new.thermal_state.value in ("hot", "critical"):
                self._fire(
                    "overheating",
                    f"Temperature rising: {new.thermal_state.value}",
                    state=new.thermal_state.value,
                )
            elif old.thermal_state.value in ("hot", "critical"):
                self._fire(
                    "cooling",
                    "Cooling down",
                    state=new.thermal_state.value,
                )
