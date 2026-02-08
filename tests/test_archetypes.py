"""Tests for Jungian archetype classes and Ego mediator."""

from unittest.mock import patch

import pytest

from sociopsi.archetypes import Anima, Archetype, Ego, Persona, SelfArchetype, Shadow
from sociopsi.archetypes.base import Archetype as BaseArchetype

# ---------------------------------------------------------------------------
# Concrete archetype subclass for testing abstract base
# ---------------------------------------------------------------------------


class StubArchetype(Archetype):
    """Concrete stub for testing the abstract base class."""

    def get_system_prompt(self) -> str:
        return "You are a test archetype."


# ---------------------------------------------------------------------------
# Archetype base class tests
# ---------------------------------------------------------------------------


class TestArchetypeBase:
    """Tests for the abstract Archetype base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            Archetype("test")  # type: ignore[abstract]

    def test_stub_initializes(self) -> None:
        arch = StubArchetype("test")
        assert arch.name == "test"
        assert arch.model == "sociopsi-mid"
        assert arch.influence_weight == 0.25

    def test_custom_model(self) -> None:
        arch = StubArchetype("test", model="custom-model")
        assert arch.model == "custom-model"

    def test_default_temperature(self) -> None:
        arch = StubArchetype("test")
        assert arch.get_temperature() == 0.7

    def test_build_prompt_includes_system_and_drives(self) -> None:
        arch = StubArchetype("test")
        drive_state = {
            "energy": {"value": 0.8, "below_threshold": False},
            "curiosity": {"value": 0.3, "below_threshold": True},
        }
        prompt = arch._build_prompt(drive_state, "somatic context")
        assert "You are a test archetype" in prompt
        assert "energy" in prompt
        assert "curiosity" in prompt
        assert "URGENT" in prompt  # curiosity is below threshold
        assert "satisfied" in prompt  # energy is satisfied
        assert "somatic context" in prompt

    def test_build_prompt_without_context(self) -> None:
        arch = StubArchetype("test")
        prompt = arch._build_prompt({"energy": {"value": 0.5}}, "")
        assert "Context:" not in prompt

    def test_build_prompt_drive_value_defaults(self) -> None:
        """Drives missing 'value' or 'below_threshold' keys use defaults."""
        arch = StubArchetype("test")
        prompt = arch._build_prompt({"mystery": {}}, "")
        assert "mystery" in prompt
        assert "0.50" in prompt  # default value
        assert "satisfied" in prompt  # default below_threshold=False

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_generate_voice_success(self, mock_chat: object) -> None:
        mock_chat.return_value = {"message": {"content": "  I feel calm.  "}}  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.generate_voice({"energy": {"value": 0.5}})
        assert result == "I feel calm."
        mock_chat.assert_called_once()  # type: ignore[attr-defined]

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_generate_voice_temperature_override(self, mock_chat: object) -> None:
        mock_chat.return_value = {"message": {"content": "override"}}  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        arch.generate_voice({"energy": {"value": 0.5}}, temperature_override=0.2)
        call_kwargs = mock_chat.call_args  # type: ignore[attr-defined]
        assert call_kwargs[1]["options"]["temperature"] == 0.2

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_generate_voice_error_returns_empty(self, mock_chat: object) -> None:
        mock_chat.side_effect = RuntimeError("connection failed")  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.generate_voice({"energy": {"value": 0.5}})
        assert result == ""

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_interpret_command(self, mock_chat: object) -> None:
        mock_chat.return_value = {"message": {"content": "Interesting command."}}  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.interpret_command("do something", {"energy": {"value": 0.5}})
        assert result == "Interesting command."

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_interpret_command_error(self, mock_chat: object) -> None:
        mock_chat.side_effect = RuntimeError("fail")  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.interpret_command("do something", {})
        assert result == ""

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_propose_goal(self, mock_chat: object) -> None:
        mock_chat.return_value = {"message": {"content": "Seek knowledge."}}  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.propose_goal(["curiosity"], {"curiosity": {"value": 0.8}})
        assert result == "Seek knowledge."

    @patch("sociopsi.archetypes.base.chat_with_retry")
    def test_propose_goal_error(self, mock_chat: object) -> None:
        mock_chat.side_effect = RuntimeError("fail")  # type: ignore[attr-defined]
        arch = StubArchetype("test")
        result = arch.propose_goal(["curiosity"], {})
        assert result == ""


# ---------------------------------------------------------------------------
# Concrete archetype tests
# ---------------------------------------------------------------------------


class TestPersona:
    """Tests for the Persona archetype."""

    def test_initialization(self) -> None:
        p = Persona()
        assert p.name == "Persona"
        assert p.model == "sociopsi-mid"

    def test_custom_model(self) -> None:
        p = Persona(model="custom")
        assert p.model == "custom"

    def test_system_prompt_content(self) -> None:
        p = Persona()
        prompt = p.get_system_prompt()
        assert "Persona" in prompt
        assert "social" in prompt.lower()

    def test_temperature(self) -> None:
        p = Persona()
        assert p.get_temperature() == 0.7

    def test_is_archetype(self) -> None:
        assert isinstance(Persona(), BaseArchetype)


class TestShadow:
    """Tests for the Shadow archetype."""

    def test_initialization(self) -> None:
        s = Shadow()
        assert s.name == "Shadow"

    def test_system_prompt_content(self) -> None:
        s = Shadow()
        prompt = s.get_system_prompt()
        assert "Shadow" in prompt
        assert "repressed" in prompt.lower() or "raw" in prompt.lower()

    def test_higher_temperature(self) -> None:
        """Shadow has higher temperature for more unpredictable responses."""
        s = Shadow()
        assert s.get_temperature() == 0.8
        assert s.get_temperature() > Persona().get_temperature()


class TestAnima:
    """Tests for the Anima archetype."""

    def test_initialization(self) -> None:
        a = Anima()
        assert a.name == "Anima"

    def test_system_prompt_content(self) -> None:
        a = Anima()
        prompt = a.get_system_prompt()
        assert "Anima" in prompt
        assert "balance" in prompt.lower() or "balancing" in prompt.lower()

    def test_temperature(self) -> None:
        a = Anima()
        assert a.get_temperature() == 0.7


class TestSelfArchetype:
    """Tests for the Self archetype."""

    def test_initialization(self) -> None:
        s = SelfArchetype()
        assert s.name == "Self"

    def test_system_prompt_content(self) -> None:
        s = SelfArchetype()
        prompt = s.get_system_prompt()
        assert "Self" in prompt
        assert "wholeness" in prompt.lower()

    def test_lower_temperature(self) -> None:
        """Self has lower temperature for grounded wisdom."""
        s = SelfArchetype()
        assert s.get_temperature() == 0.6
        assert s.get_temperature() < Persona().get_temperature()


