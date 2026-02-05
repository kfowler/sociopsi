"""Tests for archetypal dialogue system."""

import pytest
from unittest.mock import AsyncMock, Mock
from sociopsi.subsystems.archetypal_dialogue import ArchetypalDialogue
from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.memory import MemorySystem


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=OllamaClient)
    # Different responses for different archetypes
    client.generate = AsyncMock(side_effect=[
        "Persona voice",
        "Shadow voice",
        "Anima voice",
        "Self voice",
        "Ego mediated thought",
    ])
    return client


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def memory_system():
    """Create memory system."""
    return MemorySystem()


def test_archetypal_dialogue_initialization(event_bus, mock_llm_client):
    """Test dialogue system initialization."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client)

    assert dialogue.event_bus == event_bus
    assert dialogue.llm_client == mock_llm_client
    assert "persona" in dialogue.archetypes
    assert "shadow" in dialogue.archetypes
    assert "anima" in dialogue.archetypes
    assert "self" in dialogue.archetypes
    assert dialogue.ego is not None


@pytest.mark.asyncio
async def test_generate_dialogue_all_archetypes(event_bus, mock_llm_client, memory_system):
    """Test dialogue generation with all archetypes."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client, memory_system)

    drive_state = {
        "affiliation": {"value": 0.3, "below_threshold": True},
        "individuation": {"value": 0.7, "below_threshold": False},
    }

    # Track published events
    voice_events = []
    complete_events = []

    event_bus.subscribe("dialogue.archetype_voice", lambda data: voice_events.append(data))
    event_bus.subscribe("dialogue.complete", lambda data: complete_events.append(data))

    result = await dialogue.generate_dialogue(drive_state, context="User is present")

    assert result == "Ego mediated thought"

    # Should have 4 archetype voice events
    assert len(voice_events) == 4

    # Should have 1 complete event
    assert len(complete_events) == 1
    assert "harmony" in complete_events[0]
    assert "mediated_thought" in complete_events[0]

    # Should have added memory
    assert len(memory_system.memories) == 1
    assert memory_system.memories[0].content == "Ego mediated thought"


@pytest.mark.asyncio
async def test_generate_dialogue_subset_archetypes(event_bus, mock_llm_client):
    """Test dialogue with subset of archetypes."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client)

    drive_state = {
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    # Track events
    voice_events = []
    event_bus.subscribe("dialogue.archetype_voice", lambda data: voice_events.append(data))

    # Only persona and shadow
    result = await dialogue.generate_dialogue(
        drive_state,
        active_archetypes=["persona", "shadow"],
    )

    # Should only have 2 archetype voice events
    assert len(voice_events) == 2
    archetype_names = [e["archetype"] for e in voice_events]
    assert "persona" in archetype_names
    assert "shadow" in archetype_names
    assert "anima" not in archetype_names


@pytest.mark.asyncio
async def test_dialogue_includes_memory_context(event_bus, mock_llm_client, memory_system):
    """Test dialogue includes memory context."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client, memory_system)

    # Add some memories
    memory_system.add_memory("Previous interaction 1", intensity=0.8)
    memory_system.add_memory("Previous interaction 2", intensity=0.6)

    drive_state = {
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    await dialogue.generate_dialogue(drive_state, context="Current context")

    # Check that LLM was called with memory context
    # First call should be for first archetype
    call_args = mock_llm_client.generate.call_args_list[0]
    prompt = call_args[0][0]

    # Should include both current context and memory context
    assert "Current context" in prompt or "Recent context" in prompt


@pytest.mark.asyncio
async def test_dialogue_memory_intensity_based_on_harmony(event_bus, mock_llm_client, memory_system):
    """Test memory intensity based on harmony."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client, memory_system)

    drive_state = {
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    await dialogue.generate_dialogue(drive_state)

    # Should have added memory
    assert len(memory_system.memories) == 1

    # Intensity should be between 0.3 and 1.0 (based on harmony)
    memory = memory_system.memories[0]
    assert 0.3 <= memory.intensity <= 1.0


@pytest.mark.asyncio
async def test_get_state(event_bus, mock_llm_client, memory_system):
    """Test getting dialogue system state."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client, memory_system)

    # Add a memory
    memory_system.add_memory("Test memory")

    state = dialogue.get_state()

    assert "active_archetypes" in state
    assert len(state["active_archetypes"]) == 4
    assert "memory_state" in state
    assert state["memory_state"]["total_memories"] == 1


@pytest.mark.asyncio
async def test_dialogue_without_context(event_bus, mock_llm_client):
    """Test dialogue generation without context."""
    dialogue = ArchetypalDialogue(event_bus, mock_llm_client)

    drive_state = {
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    result = await dialogue.generate_dialogue(drive_state)

    # Should still work without context
    assert isinstance(result, str)
    assert len(result) > 0
