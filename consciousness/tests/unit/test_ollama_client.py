"""Tests for Ollama LLM client."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from sociopsi.llm.ollama_client import OllamaClient


@pytest.mark.asyncio
async def test_ollama_client_initialization():
    """Test Ollama client initialization."""
    client = OllamaClient(base_url="http://test:11434", model="test-model")

    assert client.base_url == "http://test:11434"
    assert client.model == "test-model"
    assert client.client is not None

    await client.close()


@pytest.mark.asyncio
async def test_generate():
    """Test text generation."""
    client = OllamaClient()

    # Mock the HTTP POST request
    mock_response = AsyncMock()
    mock_response.json = Mock(return_value={"response": "This is a test response."})
    mock_response.raise_for_status = Mock()

    with patch.object(client.client, "post", return_value=mock_response):
        response = await client.generate("Test prompt", temperature=0.5, max_tokens=50)

        assert response == "This is a test response."
        client.client.post.assert_called_once()

    await client.close()


@pytest.mark.asyncio
async def test_generate_with_defaults():
    """Test generation with default parameters."""
    client = OllamaClient()

    mock_response = AsyncMock()
    mock_response.json = Mock(return_value={"response": "Default test."})
    mock_response.raise_for_status = Mock()

    with patch.object(client.client, "post", return_value=mock_response):
        response = await client.generate("Prompt")

        assert response == "Default test."

    await client.close()
