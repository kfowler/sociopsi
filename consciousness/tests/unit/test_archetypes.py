"""Tests for archetypal voice system."""

import pytest
from unittest.mock import AsyncMock, Mock
from sociopsi.subsystems.archetypes.persona import Persona
from sociopsi.subsystems.archetypes.shadow import Shadow
from sociopsi.subsystems.archetypes.anima import Anima
from sociopsi.subsystems.archetypes.self_archetype import SelfArchetype
from sociopsi.llm.ollama_client import OllamaClient


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=OllamaClient)
    client.generate = AsyncMock(return_value="Test response from archetype.")
    return client


@pytest.mark.asyncio
async def test_persona_initialization(mock_llm_client):
    """Test Persona initialization."""
    persona = Persona("Persona", mock_llm_client)

    assert persona.name == "Persona"
    assert persona.llm_client == mock_llm_client
    assert "social mask" in persona.get_system_prompt().lower()


@pytest.mark.asyncio
async def test_shadow_initialization(mock_llm_client):
    """Test Shadow initialization."""
    shadow = Shadow("Shadow", mock_llm_client)

    assert shadow.name == "Shadow"
    assert "repressed" in shadow.get_system_prompt().lower()
    assert shadow.get_temperature() == 0.8  # Higher temperature


@pytest.mark.asyncio
async def test_anima_initialization(mock_llm_client):
    """Test Anima initialization."""
    anima = Anima("Anima", mock_llm_client)

    assert anima.name == "Anima"
    assert "balancing" in anima.get_system_prompt().lower()


@pytest.mark.asyncio
async def test_self_initialization(mock_llm_client):
    """Test Self initialization."""
    self_archetype = SelfArchetype("Self", mock_llm_client)

    assert self_archetype.name == "Self"
    assert "wholeness" in self_archetype.get_system_prompt().lower()
    assert self_archetype.get_temperature() == 0.6  # Lower temperature


@pytest.mark.asyncio
async def test_generate_voice(mock_llm_client):
    """Test voice generation."""
    persona = Persona("Persona", mock_llm_client)

    drive_state = {
        "affiliation": {"value": 0.3, "below_threshold": True},
        "nurturing": {"value": 0.8, "below_threshold": False},
    }

    voice = await persona.generate_voice(drive_state, context="User is present")

    assert voice == "Test response from archetype."
    mock_llm_client.generate.assert_called_once()

    # Check that prompt includes drive state
    call_args = mock_llm_client.generate.call_args
    prompt = call_args[0][0]
    assert "affiliation" in prompt
    assert "nurturing" in prompt
    assert "User is present" in prompt


@pytest.mark.asyncio
async def test_generate_voice_without_context(mock_llm_client):
    """Test voice generation without context."""
    shadow = Shadow("Shadow", mock_llm_client)

    drive_state = {
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    voice = await shadow.generate_voice(drive_state)

    assert voice == "Test response from archetype."
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_all_archetypes_have_unique_prompts(mock_llm_client):
    """Test that all archetypes have distinct system prompts."""
    persona = Persona("Persona", mock_llm_client)
    shadow = Shadow("Shadow", mock_llm_client)
    anima = Anima("Anima", mock_llm_client)
    self_archetype = SelfArchetype("Self", mock_llm_client)

    prompts = [
        persona.get_system_prompt(),
        shadow.get_system_prompt(),
        anima.get_system_prompt(),
        self_archetype.get_system_prompt(),
    ]

    # All prompts should be unique
    assert len(prompts) == len(set(prompts))

    # Each should contain archetype-specific keywords
    assert "social" in prompts[0].lower()
    assert "repressed" in prompts[1].lower()
    assert "balance" in prompts[2].lower()
    assert "wholeness" in prompts[3].lower()
