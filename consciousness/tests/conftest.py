"""Shared pytest fixtures for Socio-Psi tests."""

import pytest
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


@pytest.fixture
def event_bus():
    """Create a fresh event bus for testing."""
    return EventBus()


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config()


@pytest.fixture
def mock_llm_response():
    """Factory fixture for mocking LLM responses."""

    def _mock_response(response_text: str):
        """Create a mock LLM client that returns the given response."""

        class MockLLMClient:
            async def generate(self, prompt: str, **kwargs) -> str:
                return response_text

            async def close(self):
                pass

        return MockLLMClient()

    return _mock_response
