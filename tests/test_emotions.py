"""Tests for the emergent emotions system."""

import pytest

from sociopsi.config import AgentConfig
from sociopsi.drives import DriveSystem
from sociopsi.emotions import (
    EMOTION_RULES,
    EmotionState,
    EmotionSystem,
    _detect_anger,
    _detect_boredom,
    _detect_curiosity,
    _detect_fear,
    _detect_joy,
    _detect_sadness,
)
from sociopsi.modulators import ModulatorLayer


@pytest.fixture
def drive_system() -> DriveSystem:
    config = AgentConfig(voice_enabled=False)
    return DriveSystem(config)


@pytest.fixture
def modulators() -> ModulatorLayer:
    return ModulatorLayer()


@pytest.fixture
def emotion_system() -> EmotionSystem:
    return EmotionSystem()


class TestEmotionState:
    """Tests for the EmotionState dataclass."""

    def test_creation(self) -> None:
        e = EmotionState(name="joy", intensity=0.7, valence=0.9)
        assert e.name == "joy"
        assert e.intensity == 0.7
        assert e.valence == 0.9

    def test_repr(self) -> None:
        e = EmotionState(name="anger", intensity=0.5, valence=-0.8)
        r = repr(e)
        assert "anger" in r
        assert "0.50" in r
        assert "-0.80" in r


class TestDetectors:
    """Tests for individual emotion detector functions."""

    def test_anger_high_when_frustrated(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Anger emerges from high arousal + low resolution + competence frustration."""
        modulators.arousal_level = 0.9
        modulators.resolution = 0.1
        drive_system.drives["competence"].demand = 0.9
        intensity = _detect_anger(modulators, drive_system)
        assert intensity > 0.5

    def test_anger_low_when_calm_and_competent(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        modulators.arousal_level = 0.2
        modulators.resolution = 0.8
        drive_system.drives["competence"].demand = 0.1
        intensity = _detect_anger(modulators, drive_system)
        assert intensity < 0.15

    def test_fear_high_when_threatened(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Fear emerges from high arousal + certainty frustration + integrity threat."""
        modulators.arousal_level = 0.9
        drive_system.drives["certainty"].demand = 0.9
        drive_system.drives["integrity"].demand = 0.9
        intensity = _detect_fear(modulators, drive_system)
        assert intensity > 0.5

    def test_fear_low_when_safe(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        modulators.arousal_level = 0.2
        drive_system.drives["certainty"].demand = 0.1
        drive_system.drives["integrity"].demand = 0.1
        intensity = _detect_fear(modulators, drive_system)
        assert intensity < 0.15

    def test_joy_high_when_satisfied(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Joy emerges from satisfaction across drives + high resolution."""
        for d in drive_system.drives.values():
            d.demand = 0.1
        modulators.resolution = 0.9
        intensity = _detect_joy(modulators, drive_system)
        assert intensity > 0.5

    def test_joy_low_when_deprived(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        for d in drive_system.drives.values():
            d.demand = 0.8
        modulators.resolution = 0.2
        intensity = _detect_joy(modulators, drive_system)
        assert intensity < 0.15

    def test_sadness_high_when_lonely(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Sadness emerges from low arousal + affiliation frustration."""
        modulators.arousal_level = 0.1
        drive_system.drives["affiliation"].demand = 0.9
        intensity = _detect_sadness(modulators, drive_system)
        assert intensity > 0.3

    def test_sadness_low_when_connected(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        modulators.arousal_level = 0.7
        drive_system.drives["affiliation"].demand = 0.1
        intensity = _detect_sadness(modulators, drive_system)
        assert intensity < 0.15

    def test_curiosity_high_when_exploring(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Curiosity emerges from high arousal + moderate resolution + certainty frustration."""
        modulators.arousal_level = 0.8
        modulators.resolution = 0.5  # Moderate
        drive_system.drives["certainty"].demand = 0.8
        drive_system.drives["curiosity"].demand = 0.8
        intensity = _detect_curiosity(modulators, drive_system)
        assert intensity > 0.3

    def test_boredom_high_when_idle(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """Boredom emerges from low arousal + high curiosity demand."""
        modulators.arousal_level = 0.1
        modulators.resolution = 0.2
        drive_system.drives["curiosity"].demand = 0.9
        intensity = _detect_boredom(modulators, drive_system)
        assert intensity > 0.3

    def test_boredom_low_when_engaged(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        modulators.arousal_level = 0.8
        modulators.resolution = 0.7
        drive_system.drives["curiosity"].demand = 0.1
        intensity = _detect_boredom(modulators, drive_system)
        assert intensity < 0.15

    def test_all_detectors_return_0_to_1(
        self, drive_system: DriveSystem, modulators: ModulatorLayer
    ) -> None:
        """All detectors return values in [0, 1] for any input."""
        for arousal in (0.0, 0.5, 1.0):
            for res in (0.0, 0.5, 1.0):
                modulators.arousal_level = arousal
                modulators.resolution = res
                for d in drive_system.drives.values():
                    d.demand = 0.5
                for _, _, detector in EMOTION_RULES:
                    val = detector(modulators, drive_system)
                    assert 0.0 <= val <= 1.0, f"Detector returned {val}"


class TestEmotionSystem:
    """Tests for the EmotionSystem class."""

    def test_initial_state(self, emotion_system: EmotionSystem) -> None:
        assert emotion_system.current is None
        assert emotion_system.previous is None
        assert emotion_system.all_emotions == []

    def test_detects_dominant_emotion(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """System detects the strongest emotion as dominant."""
        modulators.arousal_level = 0.9
        modulators.resolution = 0.1
        drive_system.drives["competence"].demand = 0.9
        result = emotion_system.update(modulators, drive_system)
        assert result is not None
        assert result.intensity >= emotion_system.threshold

    def test_no_emotion_when_all_low(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """Returns None when all emotions below threshold."""
        # Set everything to neutral/balanced
        modulators.arousal_level = 0.5
        modulators.resolution = 0.5
        for d in drive_system.drives.values():
            d.demand = 0.3
        # With a high threshold, may return None
        emotion_system.threshold = 0.8
        result = emotion_system.update(modulators, drive_system)
        assert result is None

    def test_tracks_transitions(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """System tracks transitions between emotions."""
        # First: induce anger
        modulators.arousal_level = 0.9
        modulators.resolution = 0.1
        drive_system.drives["competence"].demand = 0.9
        emotion_system.update(modulators, drive_system)
        first = emotion_system.current

        # Then: shift to joy
        modulators.arousal_level = 0.3
        modulators.resolution = 0.9
        for d in drive_system.drives.values():
            d.demand = 0.1
        emotion_system.update(modulators, drive_system)
        second = emotion_system.current

        assert first is not None
        assert second is not None
        if first.name != second.name:
            assert emotion_system.had_transition()
            old, new = emotion_system.get_last_transition()  # type: ignore[misc]
            assert old == first.name
            assert new == second.name

    def test_get_valence(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """Valence reflects current emotion."""
        # No emotion -> 0
        assert emotion_system.get_valence() == 0.0

        # Induce joy (positive valence)
        for d in drive_system.drives.values():
            d.demand = 0.1
        modulators.resolution = 0.9
        emotion_system.update(modulators, drive_system)
        if emotion_system.current and emotion_system.current.name == "joy":
            assert emotion_system.get_valence() > 0

    def test_format_for_perception_empty(self, emotion_system: EmotionSystem) -> None:
        """No output when no emotions detected."""
        assert emotion_system.format_for_perception() == ""

    def test_format_for_perception_with_emotion(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """Perception format includes detected emotions."""
        modulators.arousal_level = 0.9
        modulators.resolution = 0.1
        drive_system.drives["competence"].demand = 0.9
        emotion_system.update(modulators, drive_system)
        text = emotion_system.format_for_perception()
        assert "[EMOTIONS]" in text
        assert "dominant:" in text

    def test_get_dialogue_context(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """Dialogue context includes emotion info."""
        modulators.arousal_level = 0.9
        drive_system.drives["competence"].demand = 0.9
        modulators.resolution = 0.1
        emotion_system.update(modulators, drive_system)
        ctx = emotion_system.get_dialogue_context()
        assert "emotion" in ctx
        assert "emotion_intensity" in ctx
        assert "emotion_valence" in ctx

    def test_get_state(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """State dict includes all expected keys."""
        modulators.arousal_level = 0.9
        drive_system.drives["competence"].demand = 0.9
        modulators.resolution = 0.1
        emotion_system.update(modulators, drive_system)
        state = emotion_system.get_state()
        assert "current" in state
        assert "intensity" in state
        assert "valence" in state
        assert "all" in state

    def test_transition_log_bounded(
        self,
        emotion_system: EmotionSystem,
        drive_system: DriveSystem,
        modulators: ModulatorLayer,
    ) -> None:
        """Transition log doesn't grow unbounded."""
        for i in range(60):
            if i % 2 == 0:
                modulators.arousal_level = 0.9
                modulators.resolution = 0.1
                drive_system.drives["competence"].demand = 0.9
                for d in drive_system.drives.values():
                    if d.name != "competence":
                        d.demand = 0.5
            else:
                modulators.arousal_level = 0.3
                modulators.resolution = 0.9
                for d in drive_system.drives.values():
                    d.demand = 0.1
            emotion_system.update(modulators, drive_system)
        assert len(emotion_system._transition_log) <= 50
