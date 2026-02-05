import pytest
import numpy as np
from sociopsi.subsystems.perception.audio import (
    AudioPerception,
    AdaptiveSampler,
    SoundClassifier
)
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    # Use default config.toml which should have audio settings
    return Config()


def test_adaptive_sampler_initialization():
    """AdaptiveSampler initializes with default FPS."""
    sampler = AdaptiveSampler()
    assert sampler.current_fps == 3.0
    assert sampler.min_fps == 1.0
    assert sampler.max_fps == 10.0


def test_adaptive_sampler_increases_on_activity():
    """FPS increases when activity detected."""
    sampler = AdaptiveSampler()
    initial_fps = sampler.current_fps

    sampler.update({"type": "speech", "volume": 0.8})

    assert sampler.current_fps > initial_fps


def test_adaptive_sampler_decreases_on_silence():
    """FPS decreases during silence."""
    sampler = AdaptiveSampler()
    sampler.current_fps = 5.0  # Start higher

    sampler.update({"type": "silence", "volume": 0.0})

    assert sampler.current_fps < 5.0


def test_sound_classifier_silence():
    """SoundClassifier detects silence."""
    classifier = SoundClassifier()

    # Very quiet audio (near zero)
    audio = np.random.randn(16000) * 0.01
    result = classifier.classify(audio)

    assert result["type"] == "silence"
    assert result["volume"] < 0.1


def test_sound_classifier_loud_noise():
    """SoundClassifier detects loud noise."""
    classifier = SoundClassifier()

    # Loud random noise
    audio = np.random.randn(16000) * 0.2
    result = classifier.classify(audio)

    assert result["type"] in ["speech", "noise"]
    assert result["volume"] > 0.5


def test_audio_perception_initialization(event_bus, config):
    """AudioPerception initializes with config."""
    audio = AudioPerception(event_bus, config)

    assert audio.sample_rate == 16000
    assert audio.chunk_size == 1024
    assert not audio.is_running
