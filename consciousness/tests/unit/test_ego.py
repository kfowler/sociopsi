"""Tests for Ego mediator."""

import pytest
from unittest.mock import AsyncMock, Mock
from sociopsi.subsystems.archetypes.ego import Ego
from sociopsi.subsystems.archetypes.persona import Persona
from sociopsi.subsystems.archetypes.shadow import Shadow
from sociopsi.llm.ollama_client import OllamaClient


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=OllamaClient)
    client.generate = AsyncMock(return_value="Integrated thought.")
    return client


@pytest.fixture
def mock_archetypes(mock_llm_client):
    """Create mock archetypes."""
    return {
        "persona": Persona("Persona", mock_llm_client),
        "shadow": Shadow("Shadow", mock_llm_client),
    }


def test_ego_initialization(mock_archetypes, mock_llm_client):
    """Test Ego initialization."""
    ego = Ego(mock_archetypes, mock_llm_client)

    assert ego.archetypes == mock_archetypes
    assert ego.llm_client == mock_llm_client


@pytest.mark.asyncio
async def test_mediate(mock_archetypes, mock_llm_client):
    """Test Ego mediation of archetypal voices."""
    ego = Ego(mock_archetypes, mock_llm_client)

    archetypal_voices = {
        "persona": "We should be polite and helpful.",
        "shadow": "We need to express our frustration.",
    }

    drive_state = {
        "individuation": {"value": 0.7, "below_threshold": False},
        "affiliation": {"value": 0.5, "below_threshold": False},
    }

    result = await ego.mediate(archetypal_voices, drive_state)

    assert result == "Integrated thought."
    mock_llm_client.generate.assert_called_once()

    # Check that prompt includes voices and individuation
    call_args = mock_llm_client.generate.call_args
    prompt = call_args[0][0]
    assert "Persona:" in prompt
    assert "Shadow:" in prompt
    assert "polite" in prompt
    assert "frustration" in prompt
    assert "0.70" in prompt  # individuation level


@pytest.mark.asyncio
async def test_mediate_low_individuation(mock_archetypes, mock_llm_client):
    """Test mediation with low individuation."""
    ego = Ego(mock_archetypes, mock_llm_client)

    archetypal_voices = {
        "persona": "Be nice.",
    }

    drive_state = {
        "individuation": {"value": 0.2, "below_threshold": True},
    }

    result = await ego.mediate(archetypal_voices, drive_state)

    assert result == "Integrated thought."

    # Check individuation level in prompt
    call_args = mock_llm_client.generate.call_args
    prompt = call_args[0][0]
    assert "0.20" in prompt


def test_calculate_harmony_empty(mock_archetypes, mock_llm_client):
    """Test harmony calculation with no voices."""
    ego = Ego(mock_archetypes, mock_llm_client)

    harmony = ego.calculate_harmony({})

    assert harmony == 0.5


def test_calculate_harmony_single_voice(mock_archetypes, mock_llm_client):
    """Test harmony calculation with single voice."""
    ego = Ego(mock_archetypes, mock_llm_client)

    voices = {"persona": "Test voice"}

    harmony = ego.calculate_harmony(voices)

    assert 0.5 <= harmony <= 1.0


def test_calculate_harmony_multiple_voices(mock_archetypes, mock_llm_client):
    """Test harmony calculation with multiple voices."""
    ego = Ego(mock_archetypes, mock_llm_client)

    voices = {
        "persona": "Voice 1",
        "shadow": "Voice 2",
        "anima": "Voice 3",
        "self": "Voice 4",
    }

    harmony = ego.calculate_harmony(voices)

    assert 0.5 <= harmony <= 1.0
    # More voices should give slightly higher harmony
    assert harmony >= 0.6
