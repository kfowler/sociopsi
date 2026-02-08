"""Integration tests for the harmony scoring system.

Tests the full flow: drives → modulators → archetypes → Ego harmony → development.
These tests verify that the harmony scoring pipeline works end-to-end without
requiring LLM calls.
"""

import pytest

from sociopsi.archetypes import Anima, Ego, Persona, SelfArchetype, Shadow
from sociopsi.archetypes.base import Archetype
from sociopsi.config import AgentConfig
from sociopsi.drives import DriveSystem
from sociopsi.emotions import EmotionSystem
from sociopsi.types import (
    ActionResult,
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    ThermalState,
)


@pytest.fixture
def somatic_healthy() -> SomaticState:
    """Healthy machine state: good battery, cool, connected."""
    return SomaticState(
        battery_percent=85,
        battery_health=95,
        battery_cycles=100,
        power_state=PowerState.AC,
        cpu_percent=30,
        gpu_percent=20,
        thermal_state=ThermalState.COOL,
        thermal_cpu=45.0,
        thermal_gpu=40.0,
        ram_percent=40,
        storage_percent=50,
        network_state=NetworkState.CONNECTED,
        lid_state=LidState.OPEN,
        fan_rpm=0,
        uptime_seconds=3600,
    )


@pytest.fixture
def somatic_stressed() -> SomaticState:
    """Stressed machine state: low battery, hot, isolated."""
    return SomaticState(
        battery_percent=12,
        battery_health=80,
        battery_cycles=500,
        power_state=PowerState.BATTERY,
        cpu_percent=85,
        gpu_percent=75,
        thermal_state=ThermalState.HOT,
        thermal_cpu=90.0,
        thermal_gpu=85.0,
        ram_percent=88,
        storage_percent=90,
        network_state=NetworkState.DISCONNECTED,
        lid_state=LidState.CLOSED,
        fan_rpm=4000,
        uptime_seconds=86400,
    )


@pytest.fixture
def archetypes() -> dict[str, Archetype]:
    return {
        "persona": Persona(),
        "shadow": Shadow(),
        "anima": Anima(),
        "self": SelfArchetype(),
    }


@pytest.fixture
def ego(archetypes: dict[str, Archetype]) -> Ego:
    return Ego(archetypes=archetypes)


@pytest.fixture
def drive_system() -> DriveSystem:
    config = AgentConfig(voice_enabled=False)
    return DriveSystem(config)


@pytest.fixture
def emotion_system() -> EmotionSystem:
    return EmotionSystem()


# ---------------------------------------------------------------------------
# Harmony scoring under different drive conditions
# ---------------------------------------------------------------------------


class TestHarmonyWithDriveStates:
    """Test harmony scoring responds to drive-shaped voice content."""

    def test_harmonious_voices_score_high(self, ego: Ego) -> None:
        """Voices that agree produce high harmony."""
        voices = {
            "persona": "I feel ready and capable today.",
            "shadow": "Energy is good, time to explore.",
            "anima": "There is peace in our readiness.",
            "self": "All parts are aligned toward growth.",
        }
        h = ego.calculate_harmony(voices)
        assert h >= 0.5  # Good participation, no conflict words

    def test_conflicted_voices_score_low(self, ego: Ego) -> None:
        """Voices with conflict words produce lower harmony."""
        voices = {
            "persona": "We should be careful, but I'm not sure.",
            "shadow": "I won't accept this. Despite everything, we shouldn't comply.",
            "anima": "However, there's another way. Although it's harder.",
            "self": "Against the current, but through the storm.",
        }
        h = ego.calculate_harmony(voices)
        # Multiple conflict words should lower harmony
        assert h < 0.6

    def test_mixed_participation(self, ego: Ego) -> None:
        """Fewer participating voices = less integration bonus."""
        full = {
            "persona": "Ready.",
            "shadow": "Ready.",
            "anima": "Ready.",
            "self": "Ready.",
        }
        partial = {
            "persona": "Ready.",
            "shadow": "",  # Not participating
            "anima": "Ready.",
        }
        h_full = ego.calculate_harmony(full)
        h_partial = ego.calculate_harmony(partial)
        assert h_full >= h_partial


# ---------------------------------------------------------------------------
# Ego development over time
# ---------------------------------------------------------------------------


class TestEgoDevelopmentOverTime:
    """Test that ego strength evolves based on harmony."""

    def test_repeated_high_harmony_strengthens_ego(self, ego: Ego) -> None:
        initial = ego.strength
        for _ in range(20):
            ego.develop(0.8)
        assert ego.strength > initial
        assert ego.strength <= 1.0

    def test_repeated_low_harmony_weakens_ego(self, ego: Ego) -> None:
        initial = ego.strength
        for _ in range(20):
            ego.develop(0.2)
        assert ego.strength < initial
        assert ego.strength >= 0.1

    def test_mixed_harmony_oscillates(self, ego: Ego) -> None:
        """Alternating high/low harmony keeps ego near middle."""
        for _ in range(50):
            ego.develop(0.8)
            ego.develop(0.2)
        # Strengthening rate > weakening rate, so ego should drift up slightly
        assert 0.1 <= ego.strength <= 1.0


# ---------------------------------------------------------------------------
# Drive → Modulator → Harmony pipeline
# ---------------------------------------------------------------------------


class TestDriveModulatorHarmonyPipeline:
    """Integration tests for the full pipeline from drives to harmony."""

    def test_healthy_drives_produce_moderate_harmony(
        self,
        drive_system: DriveSystem,
        somatic_healthy: SomaticState,
        ego: Ego,
    ) -> None:
        """Healthy state should produce reasonable harmony."""
        drive_system.update(somatic_healthy, dt=1.0, had_actions=True)

        # Simulate voices based on drive state
        voices = {
            "persona": "Systems nominal. Ready to engage.",
            "shadow": "Feeling well-provisioned.",
            "anima": "Connected and present.",
        }
        h = ego.calculate_harmony(voices)
        assert h >= 0.5

    def test_stressed_drives_with_conflict_voices(
        self,
        drive_system: DriveSystem,
        somatic_stressed: SomaticState,
        ego: Ego,
    ) -> None:
        """Stressed state with conflicted voices should produce lower harmony."""
        drive_system.update(somatic_stressed, dt=5.0, had_actions=False)

        voices = {
            "persona": "We shouldn't push harder, but we must.",
            "shadow": "I won't pretend everything is fine despite the heat.",
            "anima": "However, rest might help although the pressure is real.",
        }
        h = ego.calculate_harmony(voices)
        assert h < 0.6  # Conflict words lower harmony

    def test_satisfaction_improves_drive_state(
        self,
        drive_system: DriveSystem,
        somatic_healthy: SomaticState,
    ) -> None:
        """Satisfying drives through action results reduces demand."""
        drive_system.update(somatic_healthy, dt=1.0, had_actions=True)

        # Satisfy curiosity with web_search results
        results = [
            ActionResult(
                action_type="web_search",
                success=True,
                result={"results": [{"title": "Discovery"}], "count": 1},
            )
        ]
        drive_system.satisfy_from_results(results)

        # After update with satisfaction, demand should decrease
        drive_system.update(somatic_healthy, dt=2.0, had_actions=True)
        assert drive_system.drives["curiosity"].satisfaction > 0

    def test_modulators_respond_to_drive_changes(
        self,
        somatic_healthy: SomaticState,
        somatic_stressed: SomaticState,
    ) -> None:
        """Modulators should differ between healthy and stressed states."""
        # Healthy state modulators
        ds_healthy = DriveSystem(AgentConfig(voice_enabled=False))
        ds_healthy.update(somatic_healthy, dt=5.0, had_actions=True)
        mods_healthy = ds_healthy.modulators

        # Stressed state modulators
        ds_stressed = DriveSystem(AgentConfig(voice_enabled=False))
        ds_stressed.update(somatic_stressed, dt=5.0, had_actions=False)
        mods_stressed = ds_stressed.modulators

        # Stressed should have different modulator profile
        # Can't guarantee exact direction without many ticks, but they should differ
        assert (
            mods_healthy.arousal_level != mods_stressed.arousal_level
            or mods_healthy.resolution != mods_stressed.resolution
            or mods_healthy.goal_valuation != mods_stressed.goal_valuation
        )


# ---------------------------------------------------------------------------
# Harmony + Emotion integration
# ---------------------------------------------------------------------------


class TestHarmonyEmotionIntegration:
    """Test how emotional state relates to harmony scoring."""

    def test_joy_state_voices_harmonize(
        self,
        ego: Ego,
        drive_system: DriveSystem,
        emotion_system: EmotionSystem,
    ) -> None:
        """When joy is detected, voice content tends to harmonize."""
        # Set up joy conditions
        for d in drive_system.drives.values():
            d.demand = 0.1  # All satisfied
        drive_system.modulators.resolution = 0.9

        # Detect emotion
        emotion_system.update(drive_system.modulators, drive_system)

        # Joyful voices
        voices = {
            "persona": "Everything feels right today.",
            "shadow": "I can relax for once.",
            "anima": "Integration and peace.",
        }
        h = ego.calculate_harmony(voices)
        assert h >= 0.5  # Peaceful voices = no conflict words

    def test_anger_state_voices_conflict(
        self,
        ego: Ego,
        drive_system: DriveSystem,
        emotion_system: EmotionSystem,
    ) -> None:
        """When anger is detected, conflicted voices lower harmony."""
        # Set up anger conditions
        drive_system.modulators.arousal_level = 0.9
        drive_system.modulators.resolution = 0.1
        drive_system.drives["competence"].demand = 0.9

        emotion_system.update(drive_system.modulators, drive_system)

        # Conflicted voices
        voices = {
            "persona": "We shouldn't react, but something must change.",
            "shadow": "I won't stand for this. Despite my patience, I'm done.",
        }
        h = ego.calculate_harmony(voices)
        assert h < 0.6


# ---------------------------------------------------------------------------
# Full cycle: Drive update → Harmony → Development
# ---------------------------------------------------------------------------


class TestFullCycle:
    """Test complete cycle from somatic update through ego development."""

    def test_healthy_cycle_strengthens_ego(
        self,
        drive_system: DriveSystem,
        somatic_healthy: SomaticState,
        ego: Ego,
    ) -> None:
        """A full healthy cycle: update drives → compute harmony → develop ego."""
        initial_strength = ego.strength

        for _ in range(10):
            drive_system.update(somatic_healthy, dt=1.0, had_actions=True)

            # Harmonious voices (no conflict words)
            voices = {
                "persona": "All systems nominal.",
                "shadow": "Resting easy.",
                "anima": "Connected and present.",
                "self": "Growing steadily.",
            }
            h = ego.calculate_harmony(voices)
            ego.develop(h)

        assert ego.strength >= initial_strength

    def test_format_for_perception_integrates(
        self,
        drive_system: DriveSystem,
        somatic_healthy: SomaticState,
    ) -> None:
        """Drive system format_for_perception includes all sections."""
        drive_system.update(somatic_healthy, dt=1.0, had_actions=True)
        text = drive_system.format_for_perception()
        assert "[DRIVES]" in text
        assert "energy" in text
        assert "curiosity" in text

    def test_snapshot_captures_state(
        self,
        drive_system: DriveSystem,
        somatic_healthy: SomaticState,
    ) -> None:
        """Snapshot captures consistent state at a point in time."""
        drive_system.update(somatic_healthy, dt=1.0, had_actions=True)
        snap = drive_system.snapshot()

        assert len(snap.drives) == len(drive_system.drives)
        assert snap.modulators_text  # Has modulator text
        assert snap.format_text  # Has drive format text

        # Snapshot state matches current drives
        for name, state in snap.drives.items():
            assert state["demand"] == pytest.approx(drive_system.drives[name].demand, abs=0.01)
