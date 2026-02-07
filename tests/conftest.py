"""Pytest fixtures for sociopsi tests."""

from pathlib import Path
from typing import Any

import pytest

from sociopsi.config import AgentConfig


@pytest.fixture(autouse=True)
def _isolate_drives_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test uses a temp drives.db so production state is never loaded."""
    _original_init = AgentConfig.__init__

    def _patched_init(self: AgentConfig, **kwargs: Any) -> None:
        if "drives_db" not in kwargs:
            kwargs["drives_db"] = tmp_path / "test_drives.db"
        _original_init(self, **kwargs)

    monkeypatch.setattr(AgentConfig, "__init__", _patched_init)


@pytest.fixture
def config() -> AgentConfig:
    """Create a test configuration with voice disabled."""
    return AgentConfig(
        model="sociopsi-mid",
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
