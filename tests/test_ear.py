"""Tests for continuous speech recognition module."""

from unittest.mock import MagicMock, patch

from sociopsi.config import AgentConfig
from sociopsi.ear import Ear


class TestEarInit:
    """Tests for Ear initialization."""

    def test_initializes_with_config(self) -> None:
        """Test that Ear initializes with config."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        assert ear.config == config
        assert ear._running is False
        assert ear._backend is None

    def test_initializes_with_defaults(self) -> None:
        """Test that Ear picks up default config values."""
        config = AgentConfig(ear_enabled=True, ear_locale="en-GB", ear_on_device=False)
        ear = Ear(config)

        assert ear._enabled is True
        assert ear._locale == "en-GB"
        assert ear._on_device is False

    def test_disabled_when_config_disabled(self) -> None:
        """Test that Ear reports disabled when config says so."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        assert ear.enabled is False


class TestEarStartStop:
    """Tests for Ear start/stop methods."""

    def test_start_does_nothing_when_disabled(self) -> None:
        """Test that start() is a no-op when ear is disabled."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear.start()

        assert ear._running is False
        assert ear._backend is None

    def test_stop_does_nothing_when_not_running(self) -> None:
        """Test that stop() handles not running state gracefully."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        # Should not raise
        ear.stop()

        assert ear._running is False

    @patch("sociopsi.ear.get_speech_backend")
    def test_start_creates_backend_and_starts_listening(self, mock_get_backend: MagicMock) -> None:
        """Test that start() creates a backend and calls start_listening."""
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = True
        mock_get_backend.return_value = mock_backend

        config = AgentConfig(ear_enabled=True, ear_locale="en-US", ear_on_device=True)
        ear = Ear(config)
        ear.start()

        mock_get_backend.assert_called_once_with(locale="en-US", on_device=True)
        mock_backend.start_listening.assert_called_once()
        assert ear._running is True

    @patch("sociopsi.ear.get_speech_backend")
    def test_start_disables_when_backend_unavailable(self, mock_get_backend: MagicMock) -> None:
        """Test that start() disables ear when backend reports unavailable."""
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = False
        mock_get_backend.return_value = mock_backend

        config = AgentConfig(ear_enabled=True)
        ear = Ear(config)
        ear.start()

        assert ear._enabled is False
        assert ear._running is False

    @patch("sociopsi.ear.get_speech_backend")
    def test_stop_calls_backend_stop(self, mock_get_backend: MagicMock) -> None:
        """Test that stop() delegates to backend.stop_listening."""
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = True
        mock_get_backend.return_value = mock_backend

        config = AgentConfig(ear_enabled=True)
        ear = Ear(config)
        ear.start()
        ear.stop()

        mock_backend.stop_listening.assert_called_once()
        assert ear._running is False
        assert ear._backend is None


class TestUtteranceBuffer:
    """Tests for utterance buffering and draining."""

    def test_get_utterances_returns_empty_list_initially(self) -> None:
        """Test that get_utterances returns empty list when nothing heard."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        result = ear.get_utterances()

        assert result == []

    def test_get_utterances_drains_buffer(self) -> None:
        """Test that get_utterances atomically drains the buffer."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        # Manually add utterances to simulate recognition
        ear._utterances.append("hello world")
        ear._utterances.append("how are you")

        result = ear.get_utterances()

        assert result == ["hello world", "how are you"]
        # Buffer should be empty after drain
        assert len(ear._utterances) == 0

    def test_get_utterances_returns_in_order(self) -> None:
        """Test that utterances are returned in chronological order."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._utterances.append("first")
        ear._utterances.append("second")
        ear._utterances.append("third")

        result = ear.get_utterances()

        assert result == ["first", "second", "third"]

    def test_buffer_bounded_by_max_size(self) -> None:
        """Test that utterance buffer drops oldest when full."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        # Fill beyond max (10)
        for i in range(15):
            ear._utterances.append(f"utterance {i}")

        # Should only have last 10
        assert len(ear._utterances) == 10
        result = ear.get_utterances()
        assert result[0] == "utterance 5"
        assert result[-1] == "utterance 14"

    def test_consecutive_drains_are_independent(self) -> None:
        """Test that each drain gets only new utterances."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._utterances.append("first batch")
        first = ear.get_utterances()
        assert first == ["first batch"]

        ear._utterances.append("second batch")
        second = ear.get_utterances()
        assert second == ["second batch"]

        # No more
        third = ear.get_utterances()
        assert third == []

    def test_partial_property(self) -> None:
        """Test that partial transcription is accessible."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        assert ear.partial == ""

        ear._partial = "hello wor"
        assert ear.partial == "hello wor"


class TestSpeechCallback:
    """Tests for the _on_speech callback."""

    def test_final_result_buffers_utterance(self) -> None:
        """Test that final results are buffered."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._on_speech("hello world", is_final=True)

        assert list(ear._utterances) == ["hello world"]
        assert ear._partial == ""

    def test_partial_result_updates_partial(self) -> None:
        """Test that partial results update the partial property."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._on_speech("hel", is_final=False)

        assert ear._partial == "hel"
        assert len(ear._utterances) == 0

    def test_final_result_strips_whitespace(self) -> None:
        """Test that final results are stripped."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._on_speech("  hello  ", is_final=True)

        assert list(ear._utterances) == ["hello"]

    def test_empty_final_result_not_buffered(self) -> None:
        """Test that empty final results are dropped."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        ear._on_speech("  ", is_final=True)

        assert len(ear._utterances) == 0

    def test_final_result_publishes_event(self) -> None:
        """Test that final results publish to event bus."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        mock_handler = MagicMock()
        ear._event_bus.subscribe("perception.speech", mock_handler)

        ear._on_speech("hello", is_final=True)

        mock_handler.assert_called_once_with({"text": "hello", "is_final": True})


class TestMuteUnmute:
    """Tests for mute/unmute delegation."""

    @patch("sociopsi.ear.get_speech_backend")
    def test_mute_delegates_to_backend(self, mock_get_backend: MagicMock) -> None:
        """Test that mute delegates to backend."""
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = True
        mock_get_backend.return_value = mock_backend

        config = AgentConfig(ear_enabled=True)
        ear = Ear(config)
        ear.start()
        ear.mute()

        mock_backend.mute.assert_called_once()
        assert ear._partial == ""

    @patch("sociopsi.ear.get_speech_backend")
    def test_unmute_delegates_to_backend(self, mock_get_backend: MagicMock) -> None:
        """Test that unmute delegates to backend."""
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = True
        mock_get_backend.return_value = mock_backend

        config = AgentConfig(ear_enabled=True)
        ear = Ear(config)
        ear.start()
        ear.unmute()

        mock_backend.unmute.assert_called_once()

    def test_mute_no_backend_does_not_crash(self) -> None:
        """Test that mute is safe without a backend."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        # Should not raise
        ear.mute()
        ear.unmute()


class TestPerceptionIntegration:
    """Tests for speech perception formatting."""

    @patch("sociopsi.perception._generate_composite", return_value="All is well.")
    def test_format_perception_without_utterances(self, _mock_composite: MagicMock) -> None:
        """Test that perception works without utterances."""
        from sociopsi.perception import format_perception
        from sociopsi.types import SomaticState

        somatic = MagicMock(spec=SomaticState)
        somatic.to_tag.return_value = "[SOMATIC: test]"
        config = AgentConfig(ear_enabled=False)

        result = format_perception(
            config=config,
            somatic=somatic,
            events=[],
            action_results=[],
            heartbeat_interval=2.0,
            heartbeat_mode="idle",
        )

        assert "[SPEECH]" not in result

    @patch("sociopsi.perception._generate_composite", return_value="All is well.")
    def test_format_perception_with_utterances(self, _mock_composite: MagicMock) -> None:
        """Test that utterances appear in perception string."""
        from sociopsi.perception import format_perception
        from sociopsi.types import SomaticState

        somatic = MagicMock(spec=SomaticState)
        somatic.to_tag.return_value = "[SOMATIC: test]"
        config = AgentConfig(ear_enabled=True)

        result = format_perception(
            config=config,
            somatic=somatic,
            events=[],
            action_results=[],
            heartbeat_interval=2.0,
            heartbeat_mode="idle",
            utterances=["hello there", "what are you doing"],
        )

        assert "[SPEECH]" in result
        assert '"hello there"' in result
        assert '"what are you doing"' in result

    @patch("sociopsi.perception._generate_composite", return_value="All is well.")
    def test_format_perception_empty_utterances_omitted(self, _mock_composite: MagicMock) -> None:
        """Test that empty utterance list omits [SPEECH] section."""
        from sociopsi.perception import format_perception
        from sociopsi.types import SomaticState

        somatic = MagicMock(spec=SomaticState)
        somatic.to_tag.return_value = "[SOMATIC: test]"
        config = AgentConfig(ear_enabled=True)

        result = format_perception(
            config=config,
            somatic=somatic,
            events=[],
            action_results=[],
            heartbeat_interval=2.0,
            heartbeat_mode="idle",
            utterances=[],
        )

        assert "[SPEECH]" not in result
