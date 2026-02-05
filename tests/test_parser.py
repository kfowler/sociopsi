"""Tests for the LLM response parser."""

import pytest

from jung_agent.parser import _normalize_component, _repair_json, parse_response


class TestParseResponse:
    """Tests for parse_response function."""

    def test_parses_valid_json(self, sample_llm_response: str) -> None:
        """Test parsing a well-formed JSON response."""
        result = parse_response(sample_llm_response)

        assert len(result.stream) == 2
        assert result.stream[0].component == "anima"
        assert result.stream[0].text == "Peaceful."
        assert result.stream[1].component == "persona"
        assert result.stream[1].text == "Ready."

        assert len(result.actions) == 1
        assert result.actions[0].type == "check_battery"

    def test_extracts_json_from_markdown_code_block(self) -> None:
        """Test extraction from markdown code blocks."""
        response = """Here's my response:
```json
{"stream":[{"component":"shadow","text":"Thinking..."}],"actions":[]}
```
That's all."""
        result = parse_response(response)

        assert len(result.stream) == 1
        assert result.stream[0].component == "shadow"
        assert result.stream[0].text == "Thinking..."

    def test_extracts_json_from_surrounding_text(
        self, sample_malformed_response: str
    ) -> None:
        """Test extraction from response with surrounding text."""
        result = parse_response(sample_malformed_response)

        assert len(result.stream) == 1
        assert result.stream[0].component == "shadow"

    def test_handles_empty_response(self) -> None:
        """Test handling of empty response."""
        result = parse_response("")

        assert result.stream == []
        assert result.actions == []

    def test_handles_no_json_response(self) -> None:
        """Test handling of response with no JSON."""
        result = parse_response("This is just plain text with no JSON.")

        assert result.stream == []
        assert result.actions == []

    def test_handles_stream_as_string(self) -> None:
        """Test handling stream as a single string (malformed)."""
        response = '{"stream": "Just a thought.", "actions": []}'
        result = parse_response(response)

        assert len(result.stream) == 1
        assert result.stream[0].component == "default"
        assert result.stream[0].text == "Just a thought."

    def test_handles_stream_as_dict(self) -> None:
        """Test handling stream as a dict (malformed)."""
        response = '{"stream": {"shadow": "Dark thoughts.", "anima": "Light."}, "actions": []}'
        result = parse_response(response)

        # Should extract both components
        assert len(result.stream) == 2
        components = {s.component for s in result.stream}
        assert "shadow" in components
        assert "anima" in components

    def test_handles_multi_component_stream_items(self) -> None:
        """Test handling stream items with multiple components."""
        response = '{"stream": [{"shadow": "Dark", "persona": "Bright"}], "actions": []}'
        result = parse_response(response)

        # Should extract both components from single item
        assert len(result.stream) == 2
        components = {s.component for s in result.stream}
        assert "shadow" in components
        assert "persona" in components

    def test_extracts_action_type_from_action_key(self) -> None:
        """Test extracting action type when using 'action' key instead of 'type'."""
        response = '{"stream": [], "actions": [{"action": "look"}]}'
        result = parse_response(response)

        assert len(result.actions) == 1
        assert result.actions[0].type == "look"

    def test_extracts_action_params(self) -> None:
        """Test extracting action parameters."""
        response = '{"stream": [], "actions": [{"type": "web_search", "query": "test"}]}'
        result = parse_response(response)

        assert len(result.actions) == 1
        assert result.actions[0].type == "web_search"
        assert result.actions[0].params.get("query") == "test"


class TestNormalizeComponent:
    """Tests for component name normalization."""

    def test_normalizes_shadow_variants(self) -> None:
        """Test normalization of shadow component variants."""
        assert _normalize_component("shadow") == "shadow"
        assert _normalize_component("Shadow") == "shadow"
        assert _normalize_component("SHADOW") == "shadow"
        assert _normalize_component("the_shadow") == "shadow"

    def test_normalizes_anima_variants(self) -> None:
        """Test normalization of anima/animus variants."""
        assert _normalize_component("anima") == "anima"
        assert _normalize_component("Anima") == "anima"
        assert _normalize_component("animus") == "anima"
        assert _normalize_component("Animus") == "anima"

    def test_normalizes_persona_variants(self) -> None:
        """Test normalization of persona variants."""
        assert _normalize_component("persona") == "persona"
        assert _normalize_component("Persona") == "persona"
        assert _normalize_component("my_persona") == "persona"

    def test_normalizes_self_variants(self) -> None:
        """Test normalization of self variants."""
        assert _normalize_component("self") == "self"
        assert _normalize_component("Self") == "self"
        assert _normalize_component("the_self") == "self"

    def test_returns_default_for_unknown(self) -> None:
        """Test that unknown components return default."""
        assert _normalize_component("unknown") == "default"
        assert _normalize_component("random") == "default"
        assert _normalize_component("") == "default"


class TestRepairJson:
    """Tests for JSON repair functionality."""

    def test_removes_trailing_commas(self) -> None:
        """Test removal of trailing commas."""
        json_str = '{"stream": [{"component": "shadow",}], "actions": [],}'
        repaired = _repair_json(json_str)

        # Should be parseable after repair (check by attempting parse)
        import json

        try:
            json.loads(repaired)
            parsed = True
        except json.JSONDecodeError:
            parsed = False
        assert parsed

    def test_fixes_missing_colon_after_actions(self) -> None:
        """Test fixing missing colon after 'actions'."""
        json_str = '{"stream": [], "actions" []}'
        repaired = _repair_json(json_str)

        assert '"actions": []' in repaired

    def test_fixes_missing_colon_after_stream(self) -> None:
        """Test fixing missing colon after 'stream'."""
        json_str = '{"stream" [], "actions": []}'
        repaired = _repair_json(json_str)

        assert '"stream": []' in repaired

    def test_replaces_ellipsis_array(self) -> None:
        """Test replacement of [...] placeholder."""
        json_str = '{"stream": [...], "actions": []}'
        repaired = _repair_json(json_str)

        assert "[...]" not in repaired
        assert "[]" in repaired

    def test_replaces_ellipsis_object(self) -> None:
        """Test replacement of {...} placeholder."""
        json_str = '{"stream": [], "actions": [{...}]}'
        repaired = _repair_json(json_str)

        assert "{...}" not in repaired

    def test_removes_text_after_final_brace(self) -> None:
        """Test removal of text after final closing brace."""
        json_str = '{"stream": [], "actions": []}Some extra text'
        repaired = _repair_json(json_str)

        assert repaired.endswith("}")
        assert "Some extra text" not in repaired
