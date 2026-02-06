"""Tests for continuous speech recognition module."""

from unittest.mock import MagicMock, patch

from jung_agent.config import AgentConfig
from jung_agent.ear import Ear


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

    @patch("jung_agent.perception._generate_composite", return_value="All is well.")
    def test_format_perception_without_utterances(self, _mock_composite: MagicMock) -> None:
        """Test that perception works without utterances."""
        from jung_agent.perception import format_perception
        from jung_agent.types import SomaticState

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

    @patch("jung_agent.perception._generate_composite", return_value="All is well.")
    def test_format_perception_with_utterances(self, _mock_composite: MagicMock) -> None:
        """Test that utterances appear in perception string."""
        from jung_agent.perception import format_perception
        from jung_agent.types import SomaticState

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

    @patch("jung_agent.perception._generate_composite", return_value="All is well.")
    def test_format_perception_empty_utterances_omitted(self, _mock_composite: MagicMock) -> None:
        """Test that empty utterance list omits [SPEECH] section."""
        from jung_agent.perception import format_perception
        from jung_agent.types import SomaticState

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
