"""Tests for SomaticPoller tiered sensor polling."""

import threading
import time
from unittest.mock import MagicMock, patch

from sociopsi.sensors.somatic import (
    SomaticPoller,
    _default_state,
    gather_somatic,
)
from sociopsi.types import (
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    ThermalState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> SomaticState:
    """Build a SomaticState with sensible defaults, overriding fields."""
    from dataclasses import replace

    base = SomaticState(
        battery_percent=80,
        battery_health=95,
        battery_cycles=100,
        power_state=PowerState.AC,
        cpu_percent=20,
        gpu_percent=30,
        thermal_state=ThermalState.COOL,
        thermal_cpu=55.0,
        thermal_gpu=50.0,
        ram_percent=40,
        storage_percent=50,
        network_state=NetworkState.CONNECTED,
        lid_state=LidState.OPEN,
        fan_rpm=1200,
        uptime_seconds=3600,
    )
    return replace(base, **overrides)


# ---------------------------------------------------------------------------
# _default_state
# ---------------------------------------------------------------------------


class TestDefaultState:
    def test_returns_somatic_state(self):
        s = _default_state()
        assert isinstance(s, SomaticState)

    def test_default_values_safe(self):
        s = _default_state()
        assert s.battery_percent == 100
        assert s.power_state == PowerState.AC
        assert s.thermal_state == ThermalState.COOL
        assert s.network_state == NetworkState.DISCONNECTED
        assert s.lid_state == LidState.OPEN


# ---------------------------------------------------------------------------
# SomaticPoller: lifecycle
# ---------------------------------------------------------------------------


class TestSomaticPollerLifecycle:
    @patch("sociopsi.sensors.somatic.get_thermal_backend")
    @patch("sociopsi.sensors.somatic.get_display_backend")
    @patch("sociopsi.sensors.somatic.get_power_backend")
    @patch("sociopsi.sensors.somatic.psutil")
    def test_start_seeds_state(self, mock_psutil, mock_power, mock_display, mock_thermal):
        """After start(), snapshot returns real data, not defaults."""
        # Mock psutil
        mock_psutil.cpu_percent.return_value = 42.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=60.5)
        mock_psutil.disk_usage.return_value = MagicMock(percent=70.0)
        mock_psutil.net_if_addrs.return_value = {}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 7200

        # Mock power backend
        battery = MagicMock()
        battery.percent = 85
        battery.health = 90
        battery.cycles = 200
        battery.power_state = PowerState.BATTERY
        mock_power.return_value.get_battery.return_value = battery

        # Mock display backend
        mock_display.return_value.get_lid_state.return_value = LidState.OPEN

        # Mock thermal backend
        thermal = MagicMock()
        thermal.state = ThermalState.WARM
        thermal.cpu_temp = 65.0
        thermal.gpu_temp = 60.0
        mock_thermal.return_value.get_thermals.return_value = thermal
        mock_thermal.return_value.get_fan_speed.return_value = 2000

        poller = SomaticPoller(fast_interval=100, medium_interval=100, slow_interval=100)
        poller.start()
        try:
            snap = poller.snapshot()
            assert snap.cpu_percent == 42
            assert snap.ram_percent == 60
            assert snap.battery_percent == 85
            assert snap.power_state == PowerState.BATTERY
            assert snap.thermal_state == ThermalState.WARM
            assert snap.fan_rpm == 2000
        finally:
            poller.stop()

    def test_start_is_idempotent(self):
        """Calling start() twice doesn't create extra threads."""
        poller = SomaticPoller(fast_interval=100, medium_interval=100, slow_interval=100)
        with (
            patch.object(poller, "_poll_fast_once"),
            patch.object(poller, "_poll_medium_once"),
            patch.object(poller, "_poll_slow_once"),
        ):
            poller.start()
            assert len(poller._threads) == 3
            poller.start()
            assert len(poller._threads) == 3
            poller.stop()

    def test_stop_clears_threads(self):
        """After stop(), thread list is empty."""
        poller = SomaticPoller(fast_interval=100, medium_interval=100, slow_interval=100)
        with (
            patch.object(poller, "_poll_fast_once"),
            patch.object(poller, "_poll_medium_once"),
            patch.object(poller, "_poll_slow_once"),
        ):
            poller.start()
            assert len(poller._threads) == 3
            poller.stop()
            assert len(poller._threads) == 0
            assert not poller._running


# ---------------------------------------------------------------------------
# SomaticPoller: snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_snapshot_returns_copy(self):
        """snapshot() returns a copy, not a reference to internal state."""
        poller = SomaticPoller()
        snap1 = poller.snapshot()
        snap2 = poller.snapshot()
        assert snap1 == snap2
        assert snap1 is not snap2

    def test_snapshot_is_non_blocking(self):
        """snapshot() should be fast - no I/O, just lock + copy."""
        poller = SomaticPoller()
        start = time.monotonic()
        for _ in range(1000):
            poller.snapshot()
        elapsed = time.monotonic() - start
        # 1000 snapshots should take < 100ms (no I/O)
        assert elapsed < 0.1


# ---------------------------------------------------------------------------
# SomaticPoller: event callbacks
# ---------------------------------------------------------------------------


class TestEventCallbacks:
    def test_network_change_fires_event(self):
        """Network state change fires event callback."""
        events = []
        poller = SomaticPoller(event_callback=lambda t, d, data: events.append((t, d, data)))

        # Set initial state with network connected
        from dataclasses import replace

        with poller._lock:
            poller._state = replace(poller._state, network_state=NetworkState.CONNECTED)

        # Simulate fast poll that detects disconnection
        with patch("sociopsi.sensors.somatic.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(percent=30.0)
            mock_psutil.disk_usage.return_value = MagicMock(percent=50.0)
            mock_psutil.net_if_addrs.return_value = {}
            mock_psutil.net_if_stats.return_value = {}
            mock_psutil.boot_time.return_value = time.time() - 100

            poller._poll_fast_once()

        assert len(events) == 1
        assert events[0][0] == "network_disconnected"

    def test_battery_critical_fires_event(self):
        """Battery dropping to <=10% fires battery_critical."""
        events = []
        poller = SomaticPoller(event_callback=lambda t, d, data: events.append((t, d, data)))

        from dataclasses import replace

        with poller._lock:
            poller._state = replace(poller._state, battery_percent=15)

        battery = MagicMock()
        battery.percent = 8
        battery.health = 90
        battery.cycles = 100
        battery.power_state = PowerState.BATTERY

        with (
            patch("sociopsi.sensors.somatic.get_power_backend") as mock_power,
            patch("sociopsi.sensors.somatic.get_display_backend") as mock_display,
        ):
            mock_power.return_value.get_battery.return_value = battery
            mock_display.return_value.get_lid_state.return_value = LidState.OPEN

            poller._poll_medium_once()

        battery_events = [e for e in events if e[0] == "battery_critical"]
        assert len(battery_events) == 1
        assert battery_events[0][2]["level"] == 8

    def test_thermal_critical_fires_event(self):
        """Thermal transition to critical fires overheating event."""
        events = []
        poller = SomaticPoller(event_callback=lambda t, d, data: events.append((t, d, data)))

        from dataclasses import replace

        with poller._lock:
            poller._state = replace(poller._state, thermal_state=ThermalState.WARM)

        thermal = MagicMock()
        thermal.state = ThermalState.CRITICAL
        thermal.cpu_temp = 95.0
        thermal.gpu_temp = 90.0

        with patch("sociopsi.sensors.somatic.get_thermal_backend") as mock_thermal:
            mock_thermal.return_value.get_thermals.return_value = thermal
            mock_thermal.return_value.get_fan_speed.return_value = 5000

            poller._poll_slow_once()

        assert len(events) == 1
        assert events[0][0] == "overheating"
        assert events[0][2]["state"] == "critical"

    def test_lid_change_fires_event(self):
        """Lid state change fires lid_opened / lid_closed."""
        events = []
        poller = SomaticPoller(event_callback=lambda t, d, data: events.append((t, d, data)))

        from dataclasses import replace

        with poller._lock:
            poller._state = replace(
                poller._state,
                lid_state=LidState.OPEN,
                battery_percent=80,
                power_state=PowerState.AC,
            )

        battery = MagicMock()
        battery.percent = 80
        battery.health = 95
        battery.cycles = 100
        battery.power_state = PowerState.AC

        with (
            patch("sociopsi.sensors.somatic.get_power_backend") as mock_power,
            patch("sociopsi.sensors.somatic.get_display_backend") as mock_display,
        ):
            mock_power.return_value.get_battery.return_value = battery
            mock_display.return_value.get_lid_state.return_value = LidState.CLOSED

            poller._poll_medium_once()

        lid_events = [e for e in events if e[0] == "lid_closed"]
        assert len(lid_events) == 1

    def test_no_callback_no_crash(self):
        """Poller without callback doesn't crash on threshold crossings."""
        poller = SomaticPoller()  # No event_callback
        from dataclasses import replace

        with poller._lock:
            poller._state = replace(poller._state, network_state=NetworkState.CONNECTED)

        with patch("sociopsi.sensors.somatic.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(percent=30.0)
            mock_psutil.disk_usage.return_value = MagicMock(percent=50.0)
            mock_psutil.net_if_addrs.return_value = {}
            mock_psutil.net_if_stats.return_value = {}
            mock_psutil.boot_time.return_value = time.time() - 100

            poller._poll_fast_once()  # Should not raise


# ---------------------------------------------------------------------------
# SomaticPoller: error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    def test_fast_poll_survives_exception(self):
        """Fast tier exception doesn't crash poller or corrupt state."""
        poller = SomaticPoller()
        original = poller.snapshot()

        with patch("sociopsi.sensors.somatic.psutil") as mock_psutil:
            mock_psutil.cpu_percent.side_effect = RuntimeError("oops")
            poller._poll_fast_once()

        # State unchanged
        assert poller.snapshot() == original

    def test_medium_poll_survives_exception(self):
        """Medium tier exception doesn't crash poller."""
        poller = SomaticPoller()
        original = poller.snapshot()

        with patch("sociopsi.sensors.somatic.get_power_backend") as mock_power:
            mock_power.side_effect = RuntimeError("no battery")
            poller._poll_medium_once()

        assert poller.snapshot() == original

    def test_slow_poll_survives_exception(self):
        """Slow tier exception doesn't crash poller."""
        poller = SomaticPoller()
        original = poller.snapshot()

        with patch("sociopsi.sensors.somatic.get_thermal_backend") as mock_thermal:
            mock_thermal.side_effect = RuntimeError("no thermals")
            poller._poll_slow_once()

        assert poller.snapshot() == original


# ---------------------------------------------------------------------------
# SomaticPoller: thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_reads_and_writes(self):
        """Multiple threads reading snapshots while polls update don't crash."""
        poller = SomaticPoller()
        errors = []

        def reader():
            for _ in range(200):
                try:
                    snap = poller.snapshot()
                    assert isinstance(snap, SomaticState)
                except Exception as e:
                    errors.append(e)

        def writer():
            from dataclasses import replace

            for i in range(200):
                with poller._lock:
                    poller._state = replace(poller._state, cpu_percent=i % 100)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        threads += [threading.Thread(target=writer) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Backwards compat: gather_somatic()
# ---------------------------------------------------------------------------


class TestGatherSomatic:
    @patch("sociopsi.sensors.somatic.get_thermal_backend")
    @patch("sociopsi.sensors.somatic.get_display_backend")
    @patch("sociopsi.sensors.somatic.get_power_backend")
    @patch("sociopsi.sensors.somatic.psutil")
    def test_gather_somatic_still_works(self, mock_psutil, mock_power, mock_display, mock_thermal):
        """The legacy gather_somatic() function still returns a complete SomaticState."""
        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=45.0)
        mock_psutil.disk_usage.return_value = MagicMock(percent=55.0)
        mock_psutil.net_if_addrs.return_value = {}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 1000

        mock_power.return_value.get_battery.return_value = None
        mock_display.return_value.get_lid_state.return_value = LidState.OPEN
        mock_thermal.return_value.get_thermals.return_value = None
        mock_thermal.return_value.get_fan_speed.return_value = None

        state = gather_somatic()
        assert isinstance(state, SomaticState)
        assert state.cpu_percent == 25
        assert state.lid_state == LidState.OPEN
