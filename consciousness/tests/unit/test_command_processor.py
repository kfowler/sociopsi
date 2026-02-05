import pytest
from sociopsi.subsystems.commands.processor import CommandProcessor
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.core.config import Config
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def drive_system(event_bus):
    return DriveSystem(event_bus)


def test_command_processor_initialization(event_bus, drive_system):
    """CommandProcessor initializes and subscribes to events."""
    processor = CommandProcessor(event_bus, [], None, drive_system)
    assert processor.event_bus == event_bus
    assert processor.drive_system == drive_system


def test_calculate_psychological_state_threat(event_bus, drive_system):
    """Low drives trigger threat state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set all drives to low level
    for drive in drive_system.drives.values():
        drive.value = 0.2

    state = processor._calculate_state()
    assert state == "threat"


def test_calculate_psychological_state_calm(event_bus, drive_system):
    """High drives and harmony trigger calm state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set drives to high level
    for drive in drive_system.drives.values():
        drive.value = 0.8

    # Mock high harmony
    processor.last_harmony = 0.85

    state = processor._calculate_state()
    assert state == "calm"


def test_calculate_psychological_state_normal(event_bus, drive_system):
    """Mid-range drives trigger normal state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set drives to mid level
    for drive in drive_system.drives.values():
        drive.value = 0.5

    processor.last_harmony = 0.6

    state = processor._calculate_state()
    assert state == "normal"


def test_get_consultation_duration_ranges(event_bus, drive_system):
    """Consultation duration matches state ranges."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    threat_duration = processor._get_consultation_duration("threat")
    assert 0.5 <= threat_duration <= 1.0

    normal_duration = processor._get_consultation_duration("normal")
    assert 1.0 <= normal_duration <= 2.0

    calm_duration = processor._get_consultation_duration("calm")
    assert 2.0 <= calm_duration <= 4.0


@pytest.mark.asyncio
async def test_archetypal_interpretation(event_bus, drive_system):
    """Each archetype interprets command."""
    # Mock archetypes
    mock_archetypes = []
    for name in ["Persona", "Shadow", "Anima", "Self"]:
        archetype = MagicMock()
        archetype.name = name
        archetype.generate = AsyncMock(return_value=f"{name} interpretation")
        mock_archetypes.append(archetype)

    processor = CommandProcessor(event_bus, mock_archetypes, None, drive_system)

    interpretations = await processor._archetypal_interpretation(
        "what are you thinking?", duration=0.1
    )

    assert len(interpretations) == 4
    assert interpretations[0]["archetype"] == "Persona"
    assert "interpretation" in interpretations[0]["interpretation"]

    # Verify each archetype was called
    for archetype in mock_archetypes:
        archetype.generate.assert_called_once()


@pytest.mark.asyncio
async def test_ego_classification(event_bus, drive_system):
    """Ego synthesizes classification from interpretations."""
    mock_ego = MagicMock()
    mock_ego.generate = AsyncMock(return_value='{"type": "query", "intent": "Check drive state", "confidence": 0.9}')

    processor = CommandProcessor(event_bus, [], mock_ego, drive_system)

    interpretations = [
        {"archetype": "Persona", "interpretation": "User wants polite update"},
        {"archetype": "Shadow", "interpretation": "User is checking on us"},
    ]

    classification = await processor._ego_classification(
        "what are your drives?", interpretations
    )

    assert classification["type"] == "query"
    assert classification["intent"] == "Check drive state"
    assert classification["confidence"] == 0.9
    mock_ego.generate.assert_called_once()


def test_parse_classification_json(event_bus, drive_system):
    """Parse JSON classification response."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    json_str = '{"type": "action", "intent": "Speak thoughts", "parameters": {}, "confidence": 0.8}'
    result = processor._parse_classification(json_str)

    assert result["type"] == "action"
    assert result["intent"] == "Speak thoughts"
    assert result["confidence"] == 0.8


def test_parse_classification_fallback(event_bus, drive_system):
    """Fallback for invalid JSON."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    invalid = "Not valid JSON at all"
    result = processor._parse_classification(invalid)

    assert result["type"] == "query"  # Default
    assert result["confidence"] == 0.5


@pytest.mark.asyncio
async def test_route_command_query(event_bus, drive_system):
    """Query commands route to command.query event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.query", lambda data: published_events.append(data))

    classification = {"type": "query", "intent": "Check drives"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "query"


@pytest.mark.asyncio
async def test_route_command_action(event_bus, drive_system):
    """Action commands route to command.action event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.action", lambda data: published_events.append(data))

    classification = {"type": "action", "intent": "Speak thoughts"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "action"


@pytest.mark.asyncio
async def test_route_command_goal(event_bus, drive_system):
    """Goal commands route to command.goal event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.goal", lambda data: published_events.append(data))

    classification = {"type": "goal", "intent": "Satisfy affiliation"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "goal"
