# tests/unit/test_speech_input.py
import pytest
from sociopsi.subsystems.commands.speech_input import SpeechInput
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    # Use default config which should have audio.whisper_model set
    return Config()


def test_speech_input_initialization(event_bus, config):
    """SpeechInput initializes with config."""
    speech = SpeechInput(event_bus, config)

    # Should get model name from config or use default
    assert speech.model_name is not None
    assert not speech.is_recording
    assert speech.model is None  # Lazy load


@pytest.mark.asyncio
async def test_start_recording(event_bus, config):
    """Starting recording sets state and publishes event."""
    speech = SpeechInput(event_bus, config)

    published_events = []
    event_bus.subscribe("speech.recording.started",
                        lambda data: published_events.append(data))

    await speech.start_recording()

    assert speech.is_recording
    assert len(published_events) == 1


@pytest.mark.asyncio
async def test_stop_recording_no_audio(event_bus, config):
    """Stopping recording with no audio."""
    speech = SpeechInput(event_bus, config)
    speech.is_recording = True

    published_events = []
    event_bus.subscribe("speech.recording.stopped",
                        lambda data: published_events.append(data))

    await speech.stop_recording()

    assert not speech.is_recording
    assert len(published_events) == 1
    assert published_events[0]["transcribed"] == ""


@pytest.mark.asyncio
async def test_stop_recording_with_transcription(event_bus, config):
    """Stopping recording transcribes and publishes command."""
    speech = SpeechInput(event_bus, config)
    speech.is_recording = True
    speech.audio_buffer = [np.random.randn(16000).astype(np.float32)]

    # Mock transcription
    with patch.object(speech, 'transcribe', new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = "test command"

        command_events = []
        event_bus.subscribe("command.received",
                            lambda data: command_events.append(data))

        await speech.stop_recording()

        assert len(command_events) == 1
        assert command_events[0]["text"] == "test command"
        assert command_events[0]["source"] == "voice"
