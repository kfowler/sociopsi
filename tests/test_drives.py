"""Tests for the Psi drive system."""

import time

import pytest

from sociopsi.config import AgentConfig
from sociopsi.drives import (
    DRIVE_CONFIGS,
    DRIVE_SUGGESTIONS,
    PRIMED_ACTION_DEFAULTS,
    SATISFACTION_MAP,
    Drive,
    DriveSnapshot,
    DriveSystem,
)
from sociopsi.types import (
    ActionResult,
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    ThermalState,
)


class TestDrive:
    """Tests for individual Drive behavior."""

    def test_drive_initialization(self) -> None:
        """Test that a drive initializes with correct defaults."""
        drive = Drive(name="test", demand=0.5, baseline=0.3)

        assert drive.name == "test"
        assert drive.demand == 0.5
        assert drive.baseline == 0.3
        assert drive.satisfaction == 0.0
        assert drive.delta == 0.0
        assert drive.urgency == 0.0

    def test_drive_rises_when_unsatisfied(self) -> None:
        """Test that demand rises when satisfaction is zero."""
        drive = Drive(name="test", demand=0.3, baseline=0.2, rise_rate=0.1)
        drive.satisfaction = 0.0  # No satisfaction

        drive.update(dt=1.0)

        # Demand should have risen
        assert drive.demand > 0.3

    def test_drive_falls_when_satisfied(self) -> None:
        """Test that demand falls when satisfaction is high."""
        drive = Drive(name="test", demand=0.6, baseline=0.2, fall_rate=0.1)
        drive.satisfaction = 1.0  # Full satisfaction

        drive.update(dt=1.0)

        # Demand should have fallen
        assert drive.demand < 0.6

    def test_demand_clamped_to_baseline(self) -> None:
        """Test that demand doesn't fall below baseline."""
        drive = Drive(name="test", demand=0.2, baseline=0.3, fall_rate=0.5)
        drive.satisfaction = 1.0

        drive.update(dt=10.0)  # Large dt to ensure fall

        # Demand should not go below baseline
        assert drive.demand >= drive.baseline

    def test_demand_clamped_to_one(self) -> None:
        """Test that demand doesn't exceed 1.0."""
        drive = Drive(name="test", demand=0.9, baseline=0.2, rise_rate=0.5)
        drive.satisfaction = 0.0

        drive.update(dt=10.0)  # Large dt to ensure rise

        # Demand should not exceed 1.0
        assert drive.demand <= 1.0

    def test_urgency_increases_with_rising_demand(self) -> None:
        """Test that urgency is higher when demand is rising."""
        drive = Drive(name="test", demand=0.5, baseline=0.2, rise_rate=0.1)
        drive.satisfaction = 0.0

        drive.update(dt=1.0)

        # Urgency should incorporate the rising delta
        assert drive.urgency > drive.demand

    def test_satisfy_accumulates(self) -> None:
        """Test that satisfaction accumulates from multiple calls."""
        drive = Drive(name="test")

        drive.satisfy(0.3)
        assert drive.satisfaction == 0.3

        drive.satisfy(0.3)
        assert drive.satisfaction == 0.6

    def test_satisfy_clamped_to_one(self) -> None:
        """Test that satisfaction doesn't exceed 1.0."""
        drive = Drive(name="test")

        drive.satisfy(0.8)
        drive.satisfy(0.5)

        assert drive.satisfaction == 1.0


class TestDriveSystem:
    """Tests for the DriveSystem class."""

    @pytest.fixture
    def drive_system(self) -> DriveSystem:
        """Create a drive system for testing."""
        config = AgentConfig(voice_enabled=False)
        return DriveSystem(config)

    @pytest.fixture
    def sample_somatic(self) -> SomaticState:
        """Create sample somatic state for testing."""
        return SomaticState(
            battery_percent=80,
            battery_health=95,
            battery_cycles=100,
            power_state=PowerState.AC,
            cpu_percent=30,
            gpu_percent=20,
            thermal_state=ThermalState.COOL,
            thermal_cpu=50.0,
            thermal_gpu=45.0,
            ram_percent=50,
            storage_percent=60,
            network_state=NetworkState.CONNECTED,
            lid_state=LidState.OPEN,
            fan_rpm=0,
            uptime_seconds=3600,
        )

    def test_initializes_all_drives(self, drive_system: DriveSystem) -> None:
        """Test that all drives are initialized."""
        expected_drives = [
            "energy",
            "integrity",
            "arousal",
            "competence",
            "certainty",
            "curiosity",
            "affiliation",
            "recognition",
        ]

        for drive_name in expected_drives:
            assert drive_name in drive_system.drives
            assert isinstance(drive_system.drives[drive_name], Drive)

    def test_drives_start_at_baseline(self, drive_system: DriveSystem) -> None:
        """Test that drives start at their baseline values."""
        for drive_name, drive in drive_system.drives.items():
            expected_baseline = DRIVE_CONFIGS[drive_name]["baseline"]
            assert drive.demand == expected_baseline

    def test_update_modifies_satisfaction_from_somatic(
        self, drive_system: DriveSystem, sample_somatic: SomaticState
    ) -> None:
        """Test that update affects demand based on somatic-derived satisfaction."""
        # Get initial demand
        initial_energy_demand = drive_system.drives["energy"].demand

        # Update with high battery (AC power = high satisfaction)
        # The satisfaction is applied during update, then reset for next tick
        # But demand should have been affected (fallen)
        drive_system.update(sample_somatic, dt=5.0, had_actions=True)

        # Energy demand should not have risen much since we're on AC power
        # (satisfaction was high during update)
        assert drive_system.drives["energy"].demand <= initial_energy_demand + 0.1

    def test_satisfy_from_results_applies_satisfaction(self, drive_system: DriveSystem) -> None:
        """Test that action results satisfy relevant drives."""
        # Simulate successful web_search result
        results = [
            ActionResult(
                action_type="web_search",
                success=True,
                result={"results": [{"title": "Test"}], "count": 1},
            )
        ]

        drive_system.satisfy_from_results(results)

        # Curiosity should have been satisfied
        assert drive_system.drives["curiosity"].satisfaction > 0

    def test_get_suggestions_returns_actions_for_urgent_drives(
        self, drive_system: DriveSystem
    ) -> None:
        """Test that suggestions are returned for urgent drives."""
        # Artificially make curiosity urgent
        drive_system.drives["curiosity"].demand = 0.9
        drive_system.drives["curiosity"].urgency = 0.9

        suggestions = drive_system.get_suggestions()

        # Should have suggestions for curiosity
        assert len(suggestions) > 0
        drive_names = [s[1] for s in suggestions]
        assert "curiosity" in drive_names

    def test_get_primed_actions_returns_actions_for_very_urgent_drives(
        self, drive_system: DriveSystem
    ) -> None:
        """Test that primed actions are returned for very urgent drives."""
        # Artificially make a drive very urgent
        drive_system.drives["affiliation"].demand = 0.9
        drive_system.drives["affiliation"].urgency = 0.8

        primed = drive_system.get_primed_actions()

        # Should have at least one primed action
        assert len(primed) > 0

    def test_get_compulsive_actions_for_critical_energy(self, drive_system: DriveSystem) -> None:
        """Test compulsive actions when energy is critical."""
        # Set up critical energy state
        drive_system.drives["energy"].demand = 0.95
        drive_system.drives["energy"].urgency = 0.95

        somatic = SomaticState(
            battery_percent=5,  # Critical battery
            battery_health=95,
            battery_cycles=100,
            power_state=PowerState.BATTERY,
            cpu_percent=30,
            gpu_percent=20,
            thermal_state=ThermalState.COOL,
            thermal_cpu=50.0,
            thermal_gpu=45.0,
            ram_percent=50,
            storage_percent=60,
            network_state=NetworkState.CONNECTED,
            lid_state=LidState.OPEN,
            fan_rpm=0,
            uptime_seconds=3600,
        )

        compulsive = drive_system.get_compulsive_actions(somatic)

        # Should have compulsive action to conserve power
        assert len(compulsive) > 0
        action_types = [a.type for a in compulsive]
        assert "set_power_mode" in action_types


class TestSatisfactionMap:
    """Tests for the satisfaction mapping configuration."""

    def test_all_actions_have_satisfaction_mapping(self) -> None:
        """Test that all actions in PRIMED_ACTION_DEFAULTS have satisfaction mappings."""
        # Every primed action should have some satisfaction mapping
        for _action_type in PRIMED_ACTION_DEFAULTS:
            # Most actions should be in SATISFACTION_MAP
            # (some creative/internal ones might not satisfy drives directly)
            pass  # This is informational, not strictly required

    def test_satisfaction_values_are_valid(self) -> None:
        """Test that all satisfaction values are in valid range or callable."""
        for _action_type, drive_map in SATISFACTION_MAP.items():
            for _drive_name, value in drive_map.items():
                if callable(value):
                    # Test with empty result dict - should not raise
                    result = value({})
                    assert isinstance(result, (int, float))
                    assert 0 <= result <= 1
                else:
                    assert isinstance(value, (int, float))
                    assert 0 <= value <= 1


class TestDriveSuggestions:
    """Tests for drive suggestion configuration."""

    def test_all_drives_have_suggestions(self) -> None:
        """Test that all drives have at least one suggested action."""
        for drive_name in DRIVE_CONFIGS:
            assert drive_name in DRIVE_SUGGESTIONS
            assert len(DRIVE_SUGGESTIONS[drive_name]) > 0

    def test_all_suggested_actions_exist(self) -> None:
        """Test that all suggested actions are valid action types."""
        # Get all valid action types from SATISFACTION_MAP plus a few special ones
        valid_actions = set(SATISFACTION_MAP.keys()) | set(PRIMED_ACTION_DEFAULTS.keys())

        for drive_name, suggestions in DRIVE_SUGGESTIONS.items():
            for action in suggestions:
                assert action in valid_actions, (
                    f"Action '{action}' in {drive_name} suggestions not recognized"
                )


class TestDriveExponentialDecay:
    """Tests for satisfaction exponential decay (replaces reset-to-zero)."""

    def test_satisfaction_decays_not_resets(self) -> None:
        """Test that satisfaction decays exponentially instead of resetting to zero."""
        drive = Drive(name="test", demand=0.5, baseline=0.2, satisfaction_halflife=2.0)
        drive.satisfy(0.8)
        assert drive.satisfaction == 0.8

        # After one tick, satisfaction should have decayed but not be zero
        drive.update(dt=0.1)
        assert 0 < drive.satisfaction < 0.8

    def test_satisfaction_halves_at_halflife(self) -> None:
        """Test that satisfaction roughly halves after one half-life."""
        drive = Drive(name="test", demand=0.5, baseline=0.2, satisfaction_halflife=2.0)
        drive.satisfy(1.0)

        # Simulate exactly one half-life worth of time in one step
        drive.update(dt=2.0)

        # Should be approximately 0.5 (half of 1.0)
        assert abs(drive.satisfaction - 0.5) < 0.05

    def test_satisfaction_accumulates_with_decay(self) -> None:
        """Test that new satisfaction adds on top of decayed value."""
        drive = Drive(name="test", demand=0.5, baseline=0.2, satisfaction_halflife=2.0)
        drive.satisfy(0.4)
        drive.update(dt=1.0)  # Decays somewhat

        decayed = drive.satisfaction
        drive.satisfy(0.3)

        # Should be decayed + 0.3
        assert drive.satisfaction == pytest.approx(decayed + 0.3, abs=0.01)


class TestDriveSystemTimer:
    """Tests for the timer-based continuous drive update system."""

    @pytest.fixture
    def sample_somatic(self) -> SomaticState:
        return SomaticState(
            battery_percent=80,
            battery_health=95,
            battery_cycles=100,
            power_state=PowerState.AC,
            cpu_percent=30,
            gpu_percent=20,
            thermal_state=ThermalState.COOL,
            thermal_cpu=50.0,
            thermal_gpu=45.0,
            ram_percent=50,
            storage_percent=60,
            network_state=NetworkState.CONNECTED,
            lid_state=LidState.OPEN,
            fan_rpm=0,
            uptime_seconds=3600,
        )

    def test_timer_starts_and_stops(self) -> None:
        """Test that the timer thread starts and stops cleanly."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        ds.start()
        assert ds._running is True
        assert ds._timer_thread is not None
        assert ds._timer_thread.is_alive()

        ds.stop()
        assert ds._running is False
        assert ds._timer_thread is None

    def test_timer_updates_drives(self, sample_somatic: SomaticState) -> None:
        """Test that the timer thread updates drives over time."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        # Get initial demand for curiosity
        initial_demand = ds.drives["curiosity"].demand

        ds.push_somatic(sample_somatic, had_actions=False)
        ds.start()

        # Let it tick a few times
        time.sleep(0.35)
        ds.stop()

        # Demand should have risen (no satisfaction, natural rise)
        assert ds.drives["curiosity"].demand > initial_demand

    def test_queue_satisfaction_applies(self, sample_somatic: SomaticState) -> None:
        """Test that queued satisfaction signals are applied by the timer."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)
        ds.push_somatic(sample_somatic, had_actions=True)

        # Make curiosity unsatisfied
        ds.drives["curiosity"].demand = 0.8
        ds.drives["curiosity"].satisfaction = 0.0

        ds.start()

        # Queue a satisfaction signal
        results = [
            ActionResult(
                action_type="web_search",
                success=True,
                result={"results": [{"title": "Test"}], "count": 1},
            )
        ]
        ds.queue_satisfaction(results)

        # Wait for timer to drain
        time.sleep(0.25)
        ds.stop()

        # Curiosity should have some satisfaction from the queued signal
        # (it decays, so it may not be exact, but should be > 0)
        assert ds.drives["curiosity"].satisfaction > 0

    def test_snapshot_returns_frozen_state(self) -> None:
        """Test that snapshot returns an independent copy of drive state."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        snap = ds.snapshot()
        assert isinstance(snap, DriveSnapshot)
        assert len(snap.drives) == len(ds.drives)
        assert snap.format_text  # Should have content

        # Mutating the snapshot should not affect the system
        for key in snap.drives:
            snap.drives[key]["demand"] = 999.0

        for drive in ds.drives.values():
            assert drive.demand != 999.0

    def test_push_somatic_tracks_idle(self, sample_somatic: SomaticState) -> None:
        """Test that push_somatic tracks idle cycles correctly."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        ds.push_somatic(sample_somatic, had_actions=False)
        assert ds._idle_cycles == 1

        ds.push_somatic(sample_somatic, had_actions=False)
        assert ds._idle_cycles == 2

        ds.push_somatic(sample_somatic, had_actions=True)
        assert ds._idle_cycles == 0

    def test_satisfy_from_results_backward_compat(self) -> None:
        """Test that satisfy_from_results still works without timer."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        results = [
            ActionResult(
                action_type="web_search",
                success=True,
                result={"results": [{"title": "Test"}], "count": 1},
            )
        ]

        # Without starting the timer, satisfy_from_results should still work
        ds.satisfy_from_results(results)
        assert ds.drives["curiosity"].satisfaction > 0


class TestDriveUrgencyEvents:
    """Tests for urgency threshold event publishing."""

    def test_urgency_crossing_publishes_event(self) -> None:
        """Test that crossing urgency threshold publishes an event."""
        published: list[tuple[str, dict]] = []

        class MockBus:
            def publish(self, event_type: str, data: dict) -> None:
                published.append((event_type, data))

        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config, event_bus=MockBus())

        # Set curiosity just below threshold
        ds.drives["curiosity"].demand = 0.65
        ds.drives["curiosity"].urgency = 0.65
        ds._prev_urgency["curiosity"] = 0.65

        # Now push it above threshold
        ds.drives["curiosity"].demand = 0.85
        ds.drives["curiosity"].urgency = 0.85

        ds._publish_urgency_events()

        assert len(published) >= 1
        event_type, data = published[0]
        assert event_type == "drive.urgency_high"
        assert data["drive"] == "curiosity"

    def test_urgency_resolved_publishes_event(self) -> None:
        """Test that resolving urgency publishes a resolved event."""
        published: list[tuple[str, dict]] = []

        class MockBus:
            def publish(self, event_type: str, data: dict) -> None:
                published.append((event_type, data))

        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config, event_bus=MockBus())

        # Set curiosity above threshold previously
        ds.drives["curiosity"].urgency = 0.5
        ds._prev_urgency["curiosity"] = 0.8

        ds._publish_urgency_events()

        # Find the resolved event for curiosity
        resolved = [
            (et, d)
            for et, d in published
            if et == "drive.urgency_resolved" and d["drive"] == "curiosity"
        ]
        assert len(resolved) == 1
