"""Tests for speech action."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sociopsi.actions.speak import SpeechAction
from sociopsi.core.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def mock_tts_engine():
    """Create mock TTS engine."""
    engine = MagicMock()
    engine.setProperty = Mock()
    engine.say = Mock()
    engine.runAndWait = Mock()
    engine.stop = Mock()
    return engine


def test_speech_action_initialization(event_bus):
    """Test speech action initialization."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, enabled=True, rate=150, volume=0.9)

        assert action.event_bus == event_bus
        assert action.enabled is True
        assert action.rate == 150
        assert action.volume == 0.9
        assert action.engine is not None

        # Should have set properties
        assert mock_engine.setProperty.call_count == 2


def test_speech_action_disabled(event_bus):
    """Test speech action when disabled."""
    action = SpeechAction(event_bus, enabled=False)

    assert action.enabled is False
    assert action.engine is None


def test_speech_action_initialization_failure(event_bus):
    """Test graceful handling of TTS initialization failure."""
    with patch("pyttsx3.init", side_effect=Exception("TTS not available")):
        action = SpeechAction(event_bus, enabled=True)

        # Should gracefully disable
        assert action.enabled is False
        assert action.engine is None


def test_speak(event_bus):
    """Test speaking text."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus)
        action.speak("Hello world")

        mock_engine.say.assert_called_once_with("Hello world")
        mock_engine.runAndWait.assert_called_once()


def test_speak_when_disabled(event_bus):
    """Test speaking when disabled does nothing."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, enabled=False)
        action.speak("Hello world")

        mock_engine.say.assert_not_called()


def test_speak_failure_handling(event_bus):
    """Test handling of TTS failure."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_engine.say.side_effect = Exception("TTS error")
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus)
        # Should not raise exception
        action.speak("Hello world")


def test_on_dialogue_complete(event_bus):
    """Test that dialogue completion does NOT auto-trigger speech.

    TTS is now only triggered via explicit speak actions, not automatically
    on internal dialogue events.
    """
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus)

        # Publish dialogue complete event
        event_bus.publish(
            "dialogue.complete",
            {
                "mediated_thought": "This is the mediated thought",
                "harmony": 0.8,
            },
        )

        # Should NOT auto-speak - TTS is only triggered via explicit speak actions
        mock_engine.say.assert_not_called()


def test_on_dialogue_complete_when_disabled(event_bus):
    """Test dialogue event when TTS disabled."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, enabled=False)

        event_bus.publish(
            "dialogue.complete",
            {"mediated_thought": "Test"},
        )

        # Should not speak
        mock_engine.say.assert_not_called()


def test_set_enabled(event_bus):
    """Test enabling/disabling TTS."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, enabled=True)
        assert action.enabled is True

        action.set_enabled(False)
        assert action.enabled is False

        action.set_enabled(True)
        assert action.enabled is True


def test_set_rate(event_bus):
    """Test setting speech rate."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, rate=150)
        action.set_rate(200)

        assert action.rate == 200
        # Should have called setProperty twice: once in init, once in set_rate
        rate_calls = [call for call in mock_engine.setProperty.call_args_list if call[0][0] == "rate"]
        assert len(rate_calls) >= 1


def test_set_volume(event_bus):
    """Test setting speech volume."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, volume=0.9)
        action.set_volume(0.5)

        assert action.volume == 0.5

        # Test clamping
        action.set_volume(1.5)
        assert action.volume == 1.0

        action.set_volume(-0.5)
        assert action.volume == 0.0


def test_get_state(event_bus):
    """Test getting speech action state."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus, enabled=True, rate=150, volume=0.9)

        state = action.get_state()

        assert state["enabled"] is True
        assert state["rate"] == 150
        assert state["volume"] == 0.9
        assert state["engine_available"] is True


def test_cleanup(event_bus):
    """Test cleanup."""
    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        action = SpeechAction(event_bus)
        action.cleanup()

        mock_engine.stop.assert_called_once()


def test_cleanup_when_engine_none(event_bus):
    """Test cleanup when engine is None."""
    action = SpeechAction(event_bus, enabled=False)
    # Should not raise exception
    action.cleanup()
