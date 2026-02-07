"""Tests for continuous speech recognition module."""

from unittest.mock import MagicMock, patch

from sociopsi.config import AgentConfig
from sociopsi.ear import BENIGN_ERROR_CODES, Ear, MAX_CONSECUTIVE_ERRORS


class TestEarInit:
    """Tests for Ear initialization."""

    def test_initializes_with_config(self) -> None:
        """Test that Ear initializes with config."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        assert ear.config == config
        assert ear._running is False
        assert ear._audio_engine is None
        assert ear._recognizer is None
        assert ear._delegate is None

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
        assert ear._audio_engine is None

    def test_stop_does_nothing_when_not_running(self) -> None:
        """Test that stop() handles not running state gracefully."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)

        # Should not raise
        ear.stop()

        assert ear._running is False


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


class TestErrorHandling:
    """Tests for persistent error detection and graceful shutdown."""

    def _make_error(self, code: int = 1, description: str = "test error") -> MagicMock:
        """Create a mock NSError."""
        error = MagicMock()
        error.code.return_value = code
        error.localizedDescription.return_value = description
        return error

    def test_benign_errors_reset_counter(self) -> None:
        """Test that benign error codes (timeout, cancel) reset the error counter."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)
        ear._running = True
        ear._consecutive_errors = 2

        for code in BENIGN_ERROR_CODES:
            ear._consecutive_errors = 2
            error = self._make_error(code=code)
            ear._recognition_result_handler(None, error)
            assert ear._consecutive_errors == 0

    def test_non_benign_errors_increment_counter(self) -> None:
        """Test that non-benign errors increment the consecutive counter."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)
        ear._running = True

        error = self._make_error(code=999, description="Siri and Dictation are disabled")
        ear._recognition_result_handler(None, error)

        assert ear._consecutive_errors == 1
        assert ear._running is True  # Not yet disabled

    def test_persistent_errors_disable_ear(self) -> None:
        """Test that MAX_CONSECUTIVE_ERRORS non-benign errors disable the ear."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)
        ear._running = True
        ear._enabled = True

        error = self._make_error(code=999, description="Siri and Dictation are disabled")

        for _ in range(MAX_CONSECUTIVE_ERRORS):
            ear._recognition_result_handler(None, error)

        assert ear._enabled is False
        assert ear._running is False

    def test_successful_result_resets_error_counter(self) -> None:
        """Test that a successful final result resets the error counter."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)
        ear._running = True
        ear._consecutive_errors = 2

        result = MagicMock()
        result.isFinal.return_value = True
        result.bestTranscription.return_value.formattedString.return_value = "hello"

        ear._recognition_result_handler(result, None)

        assert ear._consecutive_errors == 0
        assert "hello" in list(ear._utterances)

    def test_partial_result_does_not_reset_counter(self) -> None:
        """Test that partial results don't reset the error counter."""
        config = AgentConfig(ear_enabled=False)
        ear = Ear(config)
        ear._running = True
        ear._consecutive_errors = 2

        result = MagicMock()
        result.isFinal.return_value = False
        result.bestTranscription.return_value.formattedString.return_value = "hel"

        ear._recognition_result_handler(result, None)

        assert ear._consecutive_errors == 2
        assert ear._partial == "hel"
