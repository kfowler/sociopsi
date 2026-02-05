"""Pytest fixtures for jung_agent tests."""

import pytest

from jung_agent.config import AgentConfig


@pytest.fixture
def config() -> AgentConfig:
    """Create a test configuration with voice disabled."""
    return AgentConfig(
        model="jung-mid",
        voice_enabled=False,  # Disable voice for tests
        heartbeat_idle=1,  # Fast heartbeat for tests
    )


@pytest.fixture
def sample_somatic_tag() -> str:
    """Sample somatic tag for testing."""
    return "[SOMATIC: battery=80%, cpu=20%, thermal=cool, ram=40%, network=connected]"


@pytest.fixture
def sample_llm_response() -> str:
    """Sample valid LLM JSON response."""
    return (
        '{"stream":['
        '{"component":"anima","text":"Peaceful."},'
        '{"component":"persona","text":"Ready."}'
        '],"actions":[{"type":"check_battery"}]}'
    )


@pytest.fixture
def sample_malformed_response() -> str:
    """Sample malformed LLM response for testing JSON repair."""
    return """I'll respond with JSON:
{"stream":[{"component":"shadow","text":"Thinking..."}],"actions":[]}
That should work."""
