"""Tests for meta-cognition system."""

import pytest
from unittest.mock import AsyncMock, Mock
from sociopsi.subsystems.metacognition import MetaCognition
from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=OllamaClient)
    client.generate = AsyncMock(return_value="I notice my thoughts are becoming more harmonious.")
    return client


def test_metacognition_initialization(event_bus, mock_llm_client):
    """Test meta-cognition initialization."""
    metacog = MetaCognition(event_bus, mock_llm_client, max_thoughts=5)

    assert metacog.event_bus == event_bus
    assert metacog.llm_client == mock_llm_client
    assert metacog.max_thoughts == 5
    assert len(metacog.recent_thoughts) == 0


def test_track_thoughts(event_bus, mock_llm_client):
    """Test tracking thoughts from dialogue events."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    # Publish dialogue event
    event_bus.publish("dialogue.complete", {
        "mediated_thought": "This is a test thought",
        "harmony": 0.8,
        "archetypal_voices": {"persona": "test", "shadow": "test"},
    })

    assert len(metacog.recent_thoughts) == 1
    assert metacog.recent_thoughts[0]["thought"] == "This is a test thought"
    assert metacog.recent_thoughts[0]["harmony"] == 0.8


def test_max_thoughts_limit(event_bus, mock_llm_client):
    """Test that max thoughts limit is respected."""
    metacog = MetaCognition(event_bus, mock_llm_client, max_thoughts=3)

    # Add more thoughts than max
    for i in range(5):
        event_bus.publish("dialogue.complete", {
            "mediated_thought": f"Thought {i}",
            "harmony": 0.5,
        })

    assert len(metacog.recent_thoughts) == 3
    # Should keep most recent
    assert metacog.recent_thoughts[-1]["thought"] == "Thought 4"


@pytest.mark.asyncio
async def test_reflect_with_thoughts(event_bus, mock_llm_client):
    """Test reflection with thoughts."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    # Add some thoughts
    event_bus.publish("dialogue.complete", {
        "mediated_thought": "First thought",
        "harmony": 0.7,
    })
    event_bus.publish("dialogue.complete", {
        "mediated_thought": "Second thought",
        "harmony": 0.8,
    })

    drive_state = {
        "affiliation": {"value": 0.6, "below_threshold": False},
        "individuation": {"value": 0.5, "below_threshold": True},
    }

    reflection = await metacog.reflect(drive_state)

    assert reflection == "I notice my thoughts are becoming more harmonious."
    mock_llm_client.generate.assert_called_once()

    # Check prompt includes key information
    call_args = mock_llm_client.generate.call_args
    prompt = call_args[0][0]
    assert "First thought" in prompt
    assert "Second thought" in prompt
    assert "affiliation" in prompt
    assert "individuation" in prompt


@pytest.mark.asyncio
async def test_reflect_without_thoughts(event_bus, mock_llm_client):
    """Test reflection without any thoughts."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    drive_state = {"affiliation": {"value": 0.5, "below_threshold": False}}

    reflection = await metacog.reflect(drive_state)

    assert reflection == "No thoughts to reflect upon yet."
    mock_llm_client.generate.assert_not_called()


@pytest.mark.asyncio
async def test_reflect_publishes_event(event_bus, mock_llm_client):
    """Test that reflection publishes event."""
    metacog = MetaCognition(event_bus, mock_llm_client)
    events = []
    event_bus.subscribe("metacognition.reflection", lambda data: events.append(data))

    event_bus.publish("dialogue.complete", {
        "mediated_thought": "Test",
        "harmony": 0.7,
    })

    drive_state = {"affiliation": {"value": 0.5, "below_threshold": False}}
    await metacog.reflect(drive_state)

    assert len(events) == 1
    assert "reflection" in events[0]
    assert "drive_state" in events[0]
    assert "thought_count" in events[0]
    assert "harmony_trend" in events[0]


def test_summarize_thoughts(event_bus, mock_llm_client):
    """Test thought summarization."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    event_bus.publish("dialogue.complete", {
        "mediated_thought": "First",
        "harmony": 0.7,
    })
    event_bus.publish("dialogue.complete", {
        "mediated_thought": "Second",
        "harmony": 0.8,
    })

    summary = metacog._summarize_thoughts()

    assert "1. First" in summary
    assert "2. Second" in summary
    assert "0.70" in summary
    assert "0.80" in summary


def test_summarize_thoughts_truncates_long(event_bus, mock_llm_client):
    """Test that long thoughts are truncated."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    long_thought = "A" * 100
    event_bus.publish("dialogue.complete", {
        "mediated_thought": long_thought,
        "harmony": 0.7,
    })

    summary = metacog._summarize_thoughts()

    # Should be truncated
    assert len(summary.split("\n")[0]) < 100
    assert "..." in summary


def test_summarize_drives(event_bus, mock_llm_client):
    """Test drive state summarization."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    drive_state = {
        "affiliation": {"value": 0.3, "below_threshold": True},
        "nurturing": {"value": 0.8, "below_threshold": False},
    }

    summary = metacog._summarize_drives(drive_state)

    assert "affiliation" in summary
    assert "0.30" in summary
    assert "needs attention" in summary
    assert "nurturing" in summary
    assert "0.80" in summary
    assert "satisfied" in summary


def test_calculate_harmony_trend_improving(event_bus, mock_llm_client):
    """Test harmony trend calculation - improving."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    # Add thoughts with increasing harmony
    for harmony in [0.3, 0.4, 0.7, 0.8]:
        event_bus.publish("dialogue.complete", {
            "mediated_thought": "test",
            "harmony": harmony,
        })

    trend = metacog._calculate_harmony_trend()

    assert trend == "improving"


def test_calculate_harmony_trend_declining(event_bus, mock_llm_client):
    """Test harmony trend calculation - declining."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    # Add thoughts with decreasing harmony
    for harmony in [0.8, 0.7, 0.4, 0.3]:
        event_bus.publish("dialogue.complete", {
            "mediated_thought": "test",
            "harmony": harmony,
        })

    trend = metacog._calculate_harmony_trend()

    assert trend == "declining"


def test_calculate_harmony_trend_stable(event_bus, mock_llm_client):
    """Test harmony trend calculation - stable."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    # Add thoughts with stable harmony
    for harmony in [0.6, 0.65, 0.6, 0.65]:
        event_bus.publish("dialogue.complete", {
            "mediated_thought": "test",
            "harmony": harmony,
        })

    trend = metacog._calculate_harmony_trend()

    assert trend == "stable"


def test_calculate_harmony_trend_insufficient_data(event_bus, mock_llm_client):
    """Test harmony trend with insufficient data."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    trend = metacog._calculate_harmony_trend()

    assert trend == "insufficient data"


def test_get_state(event_bus, mock_llm_client):
    """Test getting meta-cognition state."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    event_bus.publish("dialogue.complete", {
        "mediated_thought": "test",
        "harmony": 0.7,
    })
    event_bus.publish("dialogue.complete", {
        "mediated_thought": "test",
        "harmony": 0.9,
    })

    state = metacog.get_state()

    assert state["thought_count"] == 2
    assert state["avg_harmony"] == pytest.approx(0.8, rel=0.01)
    assert "harmony_trend" in state


def test_clear_thoughts(event_bus, mock_llm_client):
    """Test clearing thoughts."""
    metacog = MetaCognition(event_bus, mock_llm_client)

    event_bus.publish("dialogue.complete", {
        "mediated_thought": "test",
        "harmony": 0.7,
    })

    assert len(metacog.recent_thoughts) == 1

    metacog.clear_thoughts()

    assert len(metacog.recent_thoughts) == 0
