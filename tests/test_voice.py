"""Tests for voice output module."""

import threading
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

from jung_agent.config import AgentConfig
from jung_agent.types import Action, ActionResult, StreamSegment
from jung_agent.voice import Voice


class TestVoiceInit:
    """Tests for Voice initialization."""

    def test_initializes_with_config(self) -> None:
        """Test that Voice initializes with config."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert voice.config == config
        assert voice._thread is None
        assert voice._running is False

    def test_initializes_component_voices(self) -> None:
        """Test that component voice mapping is initialized."""
        config = AgentConfig(
            voice_enabled=False,
            voice_anima="TestAnima",
            voice_shadow="TestShadow",
            voice_persona="TestPersona",
            voice_self="TestSelf",
            voice_default="TestDefault",
        )
        voice = Voice(config)

        assert voice._component_voices["anima"] == "TestAnima"
        assert voice._component_voices["shadow"] == "TestShadow"
        assert voice._component_voices["persona"] == "TestPersona"
        assert voice._component_voices["self"] == "TestSelf"
        assert voice._component_voices["default"] == "TestDefault"


class TestVoiceStartStop:
    """Tests for Voice start/stop methods."""

    def test_start_does_nothing_when_voice_disabled(self) -> None:
        """Test that start() does nothing when voice is disabled."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        voice.start()

        assert voice._thread is None
        assert voice._running is False

    def test_stop_does_nothing_when_not_running(self) -> None:
        """Test that stop() handles not running state gracefully."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        # Should not raise
        voice.stop()

        assert voice._running is False

    def test_is_running_is_thread_safe(self) -> None:
        """Test that _is_running() is thread-safe."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        # Set running state
        with voice._running_lock:
            voice._running = True

        assert voice._is_running() is True

        with voice._running_lock:
            voice._running = False

        assert voice._is_running() is False


class TestSpeakStream:
    """Tests for speak_stream method."""

    def test_speak_stream_does_nothing_when_disabled(self) -> None:
        """Test that speak_stream does nothing when voice is disabled."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        segments = [StreamSegment(component="anima", text="Hello")]
        voice.speak_stream(segments)

        assert voice._queue.empty()

    def test_speak_stream_queues_segments(self) -> None:
        """Test that speak_stream queues segments when enabled."""
        config = AgentConfig(voice_enabled=True, voice_rate=200)
        voice = Voice(config)

        segments = [
            StreamSegment(component="anima", text="Hello world"),
            StreamSegment(component="shadow", text="Darkness"),
        ]
        voice.speak_stream(segments)

        # Should have 2 items in queue
        assert voice._queue.qsize() == 2

        # Check first item
        item1 = voice._queue.get_nowait()
        assert item1 is not None
        text1, voice1, rate1 = item1
        assert text1 == "Hello world"
        assert voice1 == config.voice_anima
        assert rate1 == 200

        # Check second item
        item2 = voice._queue.get_nowait()
        assert item2 is not None
        text2, voice2, rate2 = item2
        assert text2 == "Darkness"
        assert voice2 == config.voice_shadow

    def test_speak_stream_skips_short_text(self) -> None:
        """Test that speak_stream skips text that's too short after cleaning."""
        config = AgentConfig(voice_enabled=True)
        voice = Voice(config)

        segments = [
            StreamSegment(component="anima", text="Hi"),  # Too short (< 5 chars)
            StreamSegment(component="shadow", text="Hello there"),  # OK
        ]
        voice.speak_stream(segments)

        # Should only have 1 item (skipped short text)
        assert voice._queue.qsize() == 1


class TestAnnounceActions:
    """Tests for announce_actions method."""

    def test_announce_does_nothing_when_disabled(self) -> None:
        """Test that announce_actions does nothing when voice is disabled."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        actions = [Action(type="check_battery", params={})]
        voice.announce_actions(actions)

        assert voice._queue.empty()

    def test_announce_does_nothing_for_empty_list(self) -> None:
        """Test that announce_actions handles empty list."""
        config = AgentConfig(voice_enabled=True)
        voice = Voice(config)

        voice.announce_actions([])

        assert voice._queue.empty()

    def test_announce_queues_announcement(self) -> None:
        """Test that announce_actions queues announcement."""
        config = AgentConfig(voice_enabled=True)
        voice = Voice(config)

        actions = [Action(type="check_battery", params={})]
        voice.announce_actions(actions)

        assert voice._queue.qsize() == 1
        item = voice._queue.get_nowait()
        assert item is not None
        text, voice_name, rate = item
        assert "check battery" in text.lower()
        assert voice_name == config.voice_actions

    def test_announce_joins_multiple_actions(self) -> None:
        """Test that multiple actions are joined in announcement."""
        config = AgentConfig(voice_enabled=True)
        voice = Voice(config)

        actions = [
            Action(type="check_battery", params={}),
            Action(type="check_thermals", params={}),
        ]
        voice.announce_actions(actions)

        assert voice._queue.qsize() == 1
        item = voice._queue.get_nowait()
        assert item is not None
        text, _, _ = item
        assert "and" in text

    def test_announce_skips_speak_action(self) -> None:
        """Test that speak action is not announced (redundant)."""
        config = AgentConfig(voice_enabled=True)
        voice = Voice(config)

        actions = [Action(type="speak", params={"text": "Hello"})]
        voice.announce_actions(actions)

        # Should be empty since speak is skipped
        assert voice._queue.empty()


class TestCleanForSpeech:
    """Tests for _clean_for_speech method."""

    def test_removes_emphasis_markers(self) -> None:
        """Test that emphasis markers are removed."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert voice._clean_for_speech("This is *important*") == "This is important"
        assert voice._clean_for_speech("This is **very** important") == "This is very important"
        assert voice._clean_for_speech("This is _also_ important") == "This is also important"

    def test_converts_em_dash_to_pause(self) -> None:
        """Test that em-dashes are converted to commas."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert voice._clean_for_speech("Hello—world") == "Hello, world"

    def test_normalizes_whitespace(self) -> None:
        """Test that whitespace is normalized."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert voice._clean_for_speech("Hello    world") == "Hello world"
        assert voice._clean_for_speech("  Hello  ") == "Hello"

    def test_returns_empty_for_short_text(self) -> None:
        """Test that short text returns empty string."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert voice._clean_for_speech("Hi") == ""
        assert voice._clean_for_speech("A") == ""
        assert voice._clean_for_speech("    ") == ""


class TestActionToSpeech:
    """Tests for _action_to_speech method."""

    def test_formats_known_actions(self) -> None:
        """Test that known actions are formatted correctly."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        assert "brightness" in voice._action_to_speech(
            Action(type="set_brightness", params={"level": 50})
        ) or ""
        assert "volume" in voice._action_to_speech(
            Action(type="set_volume", params={"level": 30})
        ) or ""
        assert "search" in voice._action_to_speech(
            Action(type="web_search", params={"query": "test"})
        ) or ""

    def test_returns_none_for_speak_action(self) -> None:
        """Test that speak action returns None."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        result = voice._action_to_speech(Action(type="speak", params={"text": "Hello"}))
        assert result is None

    def test_returns_none_for_unknown_action(self) -> None:
        """Test that unknown actions return None."""
        config = AgentConfig(voice_enabled=False)
        voice = Voice(config)

        result = voice._action_to_speech(Action(type="unknown_action", params={}))
        assert result is None
