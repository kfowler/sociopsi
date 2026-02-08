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


# ---------------------------------------------------------------------------
# Ego tests
# ---------------------------------------------------------------------------


class TestEgo:
    """Tests for the Ego mediator class."""

    @pytest.fixture
    def archetypes(self) -> dict[str, Archetype]:
        return {
            "persona": Persona(),
            "shadow": Shadow(),
            "anima": Anima(),
            "self": SelfArchetype(),
        }

    @pytest.fixture
    def ego(self, archetypes: dict[str, Archetype]) -> Ego:
        return Ego(archetypes=archetypes)

    def test_initialization(self, ego: Ego, archetypes: dict[str, Archetype]) -> None:
        assert ego.archetypes is archetypes
        assert ego.model == "sociopsi-mid"
        assert ego.strength == 0.5
        assert ego.last_harmony == 0.5

    def test_custom_model(self, archetypes: dict[str, Archetype]) -> None:
        ego = Ego(archetypes=archetypes, model="custom")
        assert ego.model == "custom"

    def test_mediate_empty_voices(self, ego: Ego) -> None:
        """Empty voices return empty string."""
        result = ego.mediate({}, {"energy": {"value": 0.5}})
        assert result == ""

    def test_mediate_all_empty_voices(self, ego: Ego) -> None:
        """All-empty voice strings return empty string."""
        result = ego.mediate(
            {"persona": "", "shadow": ""},
            {"energy": {"value": 0.5}},
        )
        assert result == ""

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_mediate_success(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.return_value = {"message": {"content": "I find balance."}}  # type: ignore[attr-defined]
        voices = {
            "persona": "We should be careful.",
            "shadow": "Let's take the risk.",
        }
        result = ego.mediate(voices, {"individuation": {"value": 0.6}})
        assert result == "I find balance."
        mock_chat.assert_called_once()  # type: ignore[attr-defined]

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_mediate_includes_individuation(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.return_value = {"message": {"content": "ok"}}  # type: ignore[attr-defined]
        voices = {"persona": "Hello."}
        ego.mediate(voices, {"individuation": {"value": 0.7}})
        call_args = mock_chat.call_args  # type: ignore[attr-defined]
        prompt = call_args[1]["messages"][0]["content"]
        assert "0.70" in prompt  # individuation level included

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_mediate_error_returns_empty(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.side_effect = RuntimeError("fail")  # type: ignore[attr-defined]
        result = ego.mediate(
            {"persona": "Hello."},
            {"individuation": {"value": 0.5}},
        )
        assert result == ""

    # --- Harmony scoring ---

    def test_harmony_empty_voices(self, ego: Ego) -> None:
        assert ego.calculate_harmony({}) == 0.5

    def test_harmony_single_voice(self, ego: Ego) -> None:
        assert ego.calculate_harmony({"persona": "Hello."}) == 0.5

    def test_harmony_participation_bonus(self, ego: Ego) -> None:
        """More voices participating increases harmony."""
        voices_2 = {"persona": "Good.", "shadow": "Fine."}
        voices_3 = {"persona": "Good.", "shadow": "Fine.", "anima": "Nice."}
        h2 = ego.calculate_harmony(voices_2)
        h3 = ego.calculate_harmony(voices_3)
        assert h3 > h2

    def test_harmony_conflict_penalty(self, ego: Ego) -> None:
        """Conflict words decrease harmony."""
        harmonious = {"persona": "All is well.", "shadow": "I agree."}
        conflicted = {
            "persona": "We should, but however against it.",
            "shadow": "I don't agree, although.",
        }
        h_good = ego.calculate_harmony(harmonious)
        h_bad = ego.calculate_harmony(conflicted)
        assert h_bad < h_good

    def test_harmony_clamped(self, ego: Ego) -> None:
        """Harmony stays in [0.1, 1.0]."""
        # Many conflict words
        voices = {
            "persona": "but however despite although against don't won't shouldn't",
            "shadow": "but however despite although against don't won't shouldn't",
            "anima": "but however despite although against don't won't shouldn't",
        }
        h = ego.calculate_harmony(voices)
        assert 0.1 <= h <= 1.0

        # No conflict, many voices
        voices_good = {f"v{i}": f"Harmony and peace {i}." for i in range(5)}
        h2 = ego.calculate_harmony(voices_good)
        assert 0.1 <= h2 <= 1.0

    def test_harmony_updates_last_harmony(self, ego: Ego) -> None:
        voices = {"persona": "Good.", "shadow": "Good too."}
        h = ego.calculate_harmony(voices)
        assert ego.last_harmony == h

    def test_harmony_skips_empty_voices(self, ego: Ego) -> None:
        """Empty voice strings are filtered out."""
        voices = {"persona": "Hello.", "shadow": "", "anima": "World."}
        h = ego.calculate_harmony(voices)
        assert h > 0

    # --- Ego development ---

    def test_develop_strengthens_on_high_harmony(self, ego: Ego) -> None:
        initial = ego.strength
        ego.develop(0.8)
        assert ego.strength > initial

    def test_develop_weakens_on_low_harmony(self, ego: Ego) -> None:
        initial = ego.strength
        ego.develop(0.2)
        assert ego.strength < initial

    def test_develop_no_change_mid_harmony(self, ego: Ego) -> None:
        initial = ego.strength
        ego.develop(0.5)
        assert ego.strength == initial

    def test_develop_strength_clamped_high(self, ego: Ego) -> None:
        ego.strength = 0.999
        ego.develop(0.8)
        assert ego.strength <= 1.0

    def test_develop_strength_clamped_low(self, ego: Ego) -> None:
        ego.strength = 0.101
        ego.develop(0.2)
        assert ego.strength >= 0.1

    # --- Command classification ---

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_classify_command_json(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.return_value = {  # type: ignore[attr-defined]
            "message": {"content": '{"type": "query", "details": "asking about battery"}'}
        }
        result = ego.classify_command(
            "how is my battery?",
            {"persona": "checking health"},
            {"energy": {"value": 0.5}},
        )
        assert result["type"] == "query"

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_classify_command_non_json(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.return_value = {"message": {"content": "This is a query about state."}}  # type: ignore[attr-defined]
        result = ego.classify_command("status?", {}, {})
        assert result["type"] == "query"
        assert "This is a query" in result["details"]

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_classify_command_error(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.side_effect = RuntimeError("fail")  # type: ignore[attr-defined]
        result = ego.classify_command("something", {}, {})
        assert result["type"] == "query"

    # --- Goal selection ---

    def test_select_goal_empty_proposals(self, ego: Ego) -> None:
        assert ego.select_goal({}, {}) is None

    def test_select_goal_all_empty_proposals(self, ego: Ego) -> None:
        assert ego.select_goal({"persona": "", "shadow": ""}, {}) is None

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_select_goal_success(self, mock_chat: object, ego: Ego) -> None:
        mock_chat.return_value = {"message": {"content": "Explore the network."}}  # type: ignore[attr-defined]
        result = ego.select_goal(
            {"persona": "Check status.", "shadow": "Break free."},
            {"curiosity": {"value": 0.8, "below_threshold": True}},
        )
        assert result == "Explore the network."

    @patch("sociopsi.archetypes.ego.chat_with_retry")
    def test_select_goal_error_falls_back(self, mock_chat: object, ego: Ego) -> None:
        """On error, falls back to first non-empty proposal."""
        mock_chat.side_effect = RuntimeError("fail")  # type: ignore[attr-defined]
        result = ego.select_goal(
            {"persona": "", "shadow": "Break free."},
            {},
        )
        assert result == "Break free."
