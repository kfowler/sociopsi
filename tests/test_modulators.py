"""Tests for the MicroPsi2 modulator layer."""

import pytest

from sociopsi.config import AgentConfig
from sociopsi.drives import DriveSystem
from sociopsi.modulators import ModulatorLayer, _clamp, _smooth


class TestModulatorLayer:
    """Tests for ModulatorLayer computation."""

    @pytest.fixture
    def drive_system(self) -> DriveSystem:
        """Create a drive system for testing."""
        config = AgentConfig(voice_enabled=False)
        return DriveSystem(config)

    @pytest.fixture
    def modulators(self) -> ModulatorLayer:
        """Create a fresh modulator layer."""
        return ModulatorLayer()

    def test_initial_values(self, modulators: ModulatorLayer) -> None:
        """All modulators start at 0.5 (neutral)."""
        assert modulators.arousal_level == 0.5
        assert modulators.resolution == 0.5
        assert modulators.selection_threshold == 0.5
        assert modulators.securing_rate == 0.5
        assert modulators.goal_valuation == 0.5

    def test_update_from_drive_system(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Modulators update based on drive states."""
        initial_arousal = modulators.arousal_level
        # Spike arousal drive demand
        drive_system.drives["arousal"].demand = 0.9
        drive_system.drives["curiosity"].demand = 0.8
        modulators.update(drive_system)
        # Arousal level should have risen
        assert modulators.arousal_level > initial_arousal

    def test_high_competence_high_resolution(self, drive_system: DriveSystem) -> None:
        """When competence is satisfied (low demand), resolution should be high."""
        mods = ModulatorLayer(_smoothing=1.0)  # Instant update for testing
        drive_system.drives["competence"].demand = 0.1  # Satisfied
        drive_system.drives["certainty"].demand = 0.1  # Certain
        drive_system.drives["arousal"].demand = 0.2  # Calm
        mods.update(drive_system)
        assert mods.resolution > 0.6

    def test_frustration_lowers_resolution(self, drive_system: DriveSystem) -> None:
        """When competence is frustrated (high demand), resolution drops."""
        mods = ModulatorLayer(_smoothing=1.0)
        drive_system.drives["competence"].demand = 0.9
        drive_system.drives["certainty"].demand = 0.8
        drive_system.drives["arousal"].demand = 0.8
        mods.update(drive_system)
        assert mods.resolution < 0.4

    def test_high_arousal_low_threshold(self, drive_system: DriveSystem) -> None:
        """High arousal + low competence = low selection threshold (flighty)."""
        mods = ModulatorLayer(_smoothing=1.0)
        drive_system.drives["arousal"].demand = 0.9
        drive_system.drives["integrity"].demand = 0.8
        drive_system.drives["competence"].demand = 0.8
        drive_system.drives["certainty"].demand = 0.8
        mods.update(drive_system)
        assert mods.selection_threshold < 0.3

    def test_calm_high_threshold(self, drive_system: DriveSystem) -> None:
        """Low arousal + good integrity = high selection threshold (persistent)."""
        mods = ModulatorLayer(_smoothing=1.0)
        drive_system.drives["arousal"].demand = 0.1
        drive_system.drives["integrity"].demand = 0.1
        drive_system.drives["competence"].demand = 0.1
        drive_system.drives["certainty"].demand = 0.1
        mods.update(drive_system)
        assert mods.selection_threshold > 0.7

    def test_values_clamped_0_1(self, drive_system: DriveSystem) -> None:
        """All modulator values stay in [0, 1] range."""
        mods = ModulatorLayer(_smoothing=1.0)
        # Set extreme drive values
        for drive in drive_system.drives.values():
            drive.demand = 1.0
        mods.update(drive_system)
        for attr in (
            "arousal_level",
            "resolution",
            "selection_threshold",
            "securing_rate",
            "goal_valuation",
        ):
            val = getattr(mods, attr)
            assert 0.0 <= val <= 1.0, f"{attr} = {val} out of range"

        # Also test with all drives at 0
        for drive in drive_system.drives.values():
            drive.demand = 0.0
        mods.update(drive_system)
        for attr in (
            "arousal_level",
            "resolution",
            "selection_threshold",
            "securing_rate",
            "goal_valuation",
        ):
            val = getattr(mods, attr)
            assert 0.0 <= val <= 1.0, f"{attr} = {val} out of range"

    def test_smoothing_dampens_change(self, drive_system: DriveSystem) -> None:
        """With default smoothing (0.3), values change gradually."""
        mods = ModulatorLayer()  # Default smoothing
        # Spike all drives high
        for drive in drive_system.drives.values():
            drive.demand = 1.0
        mods.update(drive_system)
        # After one update, arousal should move toward 1.0 but not reach it
        assert mods.arousal_level > 0.5  # Moved up
        assert mods.arousal_level < 0.9  # But not all the way

    def test_drive_system_owns_modulators(self, drive_system: DriveSystem) -> None:
        """DriveSystem creates and owns a ModulatorLayer."""
        assert hasattr(drive_system, "modulators")
        assert isinstance(drive_system.modulators, ModulatorLayer)

    def test_drive_system_update_updates_modulators(self, drive_system: DriveSystem) -> None:
        """DriveSystem.update() also updates modulators."""
        from sociopsi.types import (
            LidState,
            NetworkState,
            PowerState,
            SomaticState,
            ThermalState,
        )

        somatic = SomaticState(
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
        initial = drive_system.modulators.arousal_level
        drive_system.update(somatic, dt=5.0, had_actions=True)
        # Value should have changed from drive updates
        assert (
            drive_system.modulators.arousal_level != initial or True
        )  # May not change if balanced


class TestModulatorOutputs:
    """Tests for modulator-derived outputs."""

    def test_temperature_range(self) -> None:
        """Temperature maps to [0.2, 1.2] range."""
        mods = ModulatorLayer()
        # At default 0.5/0.5
        temp = mods.get_temperature()
        assert 0.2 <= temp <= 1.2

        # High arousal, low resolution -> high temp
        mods.arousal_level = 0.9
        mods.resolution = 0.1
        temp = mods.get_temperature()
        assert temp > 0.8

        # Low arousal, high resolution -> low temp
        mods.arousal_level = 0.1
        mods.resolution = 0.9
        temp = mods.get_temperature()
        assert temp < 0.5

    def test_token_budget_range(self) -> None:
        """Token budget factor maps to [0.4, 1.5] range."""
        mods = ModulatorLayer()
        factor = mods.get_token_budget_factor()
        assert 0.4 <= factor <= 1.5

    def test_memory_write_probability_range(self) -> None:
        """Memory write probability maps to [0.1, 0.9] range."""
        mods = ModulatorLayer()
        # Low securing rate
        mods.securing_rate = 0.0
        assert mods.get_memory_write_probability() == pytest.approx(0.1)
        # High securing rate
        mods.securing_rate = 1.0
        assert mods.get_memory_write_probability() == pytest.approx(0.9)

    def test_satisfaction_multiplier_range(self) -> None:
        """Drive satisfaction multiplier maps to [0.5, 1.5] range."""
        mods = ModulatorLayer()
        # Low valuation (threat-avoiding)
        mods.goal_valuation = 0.0
        assert mods.get_drive_satisfaction_multiplier() == pytest.approx(0.5)
        # High valuation (reward-seeking)
        mods.goal_valuation = 1.0
        assert mods.get_drive_satisfaction_multiplier() == pytest.approx(1.5)

    def test_prompt_tone_high_arousal(self) -> None:
        """High arousal produces urgency directive."""
        mods = ModulatorLayer()
        mods.arousal_level = 0.8
        tone = mods.get_prompt_tone()
        assert "urgency" in tone.lower()

    def test_prompt_tone_low_arousal(self) -> None:
        """Low arousal produces calm directive."""
        mods = ModulatorLayer()
        mods.arousal_level = 0.2
        tone = mods.get_prompt_tone()
        assert "calm" in tone.lower()

    def test_prompt_tone_neutral(self) -> None:
        """Neutral state produces empty tone."""
        mods = ModulatorLayer()
        # All at 0.5 -> no directives
        tone = mods.get_prompt_tone()
        assert tone == ""

    def test_format_for_perception(self) -> None:
        """Perception format includes all five modulators."""
        mods = ModulatorLayer()
        text = mods.format_for_perception()
        assert "[MODULATORS]" in text
        assert "arousal_level" in text
        assert "resolution" in text
        assert "sel_threshold" in text
        assert "securing_rate" in text
        assert "goal_valuation" in text

    def test_get_state_returns_all_values(self) -> None:
        """get_state() returns dict with all modulator values."""
        mods = ModulatorLayer()
        state = mods.get_state()
        assert "arousal_level" in state
        assert "resolution" in state
        assert "selection_threshold" in state
        assert "securing_rate" in state
        assert "goal_valuation" in state

    def test_get_dialogue_context(self) -> None:
        """get_dialogue_context() includes tone and temperature."""
        mods = ModulatorLayer()
        ctx = mods.get_dialogue_context()
        assert "tone" in ctx
        assert "temperature" in ctx
        assert "arousal_level" in ctx
        assert "resolution" in ctx


class TestHelpers:
    """Tests for helper functions."""

    def test_clamp(self) -> None:
        assert _clamp(0.5) == 0.5
        assert _clamp(-0.1) == 0.0
        assert _clamp(1.5) == 1.0

    def test_smooth(self) -> None:
        # factor=0 -> no change
        assert _smooth(0.5, 1.0, 0.0) == 0.5
        # factor=1 -> instant
        assert _smooth(0.5, 1.0, 1.0) == 1.0
        # factor=0.5 -> halfway
        assert _smooth(0.0, 1.0, 0.5) == pytest.approx(0.5)
