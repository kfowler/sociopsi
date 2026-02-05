import pytest
from sociopsi.subsystems.commands.query_handler import QueryHandler
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.drives import Drive, DriveSystem
from sociopsi.subsystems.memory import Memory, MemorySystem
from sociopsi.core.config import Config
from unittest.mock import MagicMock


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_agent():
    agent = MagicMock()

    # Mock drive system - code uses drives.values() dict access
    drive1 = Drive("affiliation", decay_rate=0.01, base_threshold=0.4)
    drive1.value = 0.6
    drive2 = Drive("nurturing", decay_rate=0.008, base_threshold=0.3)
    drive2.value = 0.8
    agent.drive_system.drives = {"affiliation": drive1, "nurturing": drive2}

    # Mock memory system
    agent.memory_system.get_recent_memories.return_value = [
        Memory(content="Thought about nature", intensity=0.7),
        Memory(content="Reflected on harmony", intensity=0.8),
    ]

    # Mock dialogue.ego - code uses agent.dialogue.ego.last_harmony_level
    agent.dialogue.ego.last_harmony_level = 0.75

    # Mock goal manager
    agent.goal_manager.get_active_goals.return_value = []

    return agent


def test_query_handler_initialization(event_bus, mock_agent):
    """QueryHandler initializes and subscribes to events."""
    handler = QueryHandler(event_bus, mock_agent)
    assert handler.event_bus == event_bus
    assert handler.agent == mock_agent


@pytest.mark.asyncio
async def test_query_drives(event_bus, mock_agent):
    """Query drives returns current drive levels."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "what are your drives"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "affiliation" in response.lower()
    assert "0.6" in response or "0.60" in response


@pytest.mark.asyncio
async def test_query_thoughts(event_bus, mock_agent):
    """Query thoughts returns recent memories."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "what are you thinking"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "nature" in response.lower() or "harmony" in response.lower()


@pytest.mark.asyncio
async def test_query_harmony(event_bus, mock_agent):
    """Query harmony returns harmony level."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "how is your harmony"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "0.75" in response or "harmony" in response.lower()
