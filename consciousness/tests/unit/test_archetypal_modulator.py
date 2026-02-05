import pytest
from sociopsi.subsystems.archetypes.modulator import ArchetypalModulator
from sociopsi.core.event_bus import EventBus
from unittest.mock import MagicMock


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_archetypes():
    return {
        "persona": MagicMock(),
        "shadow": MagicMock(),
        "anima": MagicMock(),
        "self": MagicMock()
    }


def test_modulator_initialization(event_bus, mock_archetypes):
    """ArchetypalModulator initializes with base weights."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    assert modulator.current_weights["persona"] == 1.0
    assert modulator.current_weights["shadow"] == 1.0
    assert modulator.current_weights["anima"] == 1.0
    assert modulator.current_weights["self"] == 1.0


def test_modulator_silence_boosts_self(event_bus, mock_archetypes):
    """Silence environment boosts Self and Anima."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    # Publish silence event
    event_bus.publish("perception.audio.ambient", {
        "type": "silence",
        "volume": 0.0,
        "confidence": 0.95
    })

    # Self should be boosted
    assert modulator.current_weights["self"] > 1.0
    assert modulator.current_weights["anima"] > 1.0
    assert modulator.current_weights["shadow"] < 1.0


def test_modulator_speech_boosts_anima(event_bus, mock_archetypes):
    """Speech environment boosts Anima and Persona."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    event_bus.publish("perception.audio.ambient", {
        "type": "speech",
        "volume": 0.6,
        "confidence": 0.8
    })

    assert modulator.current_weights["anima"] > 1.0
    assert modulator.current_weights["persona"] > 1.0


def test_modulator_loud_noise_boosts_shadow(event_bus, mock_archetypes):
    """Loud noise boosts Shadow (survival mode)."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    event_bus.publish("perception.audio.ambient", {
        "type": "noise",
        "volume": 0.9,
        "confidence": 0.7
    })

    assert modulator.current_weights["shadow"] > 1.0


def test_modulator_smooth_transitions(event_bus, mock_archetypes):
    """Weight transitions are smooth, not abrupt."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    initial_self = modulator.current_weights["self"]

    # Single silence event shouldn't jump to 1.5 immediately
    event_bus.publish("perception.audio.ambient", {
        "type": "silence",
        "volume": 0.0,
        "confidence": 0.95
    })

    # Should be between initial and target
    assert initial_self < modulator.current_weights["self"] < 1.5
