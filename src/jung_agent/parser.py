"""Parse responses from the psyche."""

import json
import re

from jung_agent.types import Action, PsycheResponse


def parse_response(response: str) -> PsycheResponse:
    """Parse the psyche's JSON response into stream and actions."""
    stream_items: list[dict[str, str]] = []
    actions: list[Action] = []

    # Try to parse as pure JSON first (new format)
    try:
        # Find JSON object in response (may have whitespace around it)
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            data = json.loads(json_match.group())

            # Extract stream items
            for item in data.get("stream", []):
                component = item.get("component", "default")
                text = item.get("text", "")
                if text:
                    # Strip redundant component names from start of text
                    text = re.sub(r"^(SHADOW|ANIMA|ANIMUS|PERSONA|SELF)[:\s]*", "", text, flags=re.IGNORECASE).strip()
                    if text:
                        stream_items.append({"component": component, "text": text})

            # Extract actions
            for action_dict in data.get("actions", []):
                action_type = action_dict.pop("type", None)
                if action_type:
                    actions.append(Action(type=action_type, params=action_dict))

            # Build stream string with component markers for display/voice
            stream_parts = []
            for item in stream_items:
                comp = item["component"].upper()
                stream_parts.append(f"[{comp}] {item['text']}")
            stream = "\n".join(stream_parts)

            return PsycheResponse(stream=stream, actions=actions, raw=response)

    except json.JSONDecodeError:
        pass

    # Fallback: try old [STREAM]/[ACTIONS] format
    return _parse_legacy_format(response)


def _parse_legacy_format(response: str) -> PsycheResponse:
    """Parse old [STREAM]/[ACTIONS] format for backward compatibility."""
    stream = ""
    actions: list[Action] = []

    # Match [ACTIONS] followed by JSON
    actions_pattern = r"\[ACTIONS\]\s*(\{[\s\S]*\})"
    actions_match = re.search(actions_pattern, response, re.IGNORECASE)

    if actions_match:
        try:
            actions_json = actions_match.group(1)
            actions_json = _clean_json(actions_json)
            actions_data = json.loads(actions_json)

            for action_dict in actions_data.get("actions", []):
                action_type = action_dict.pop("type", None)
                if action_type:
                    actions.append(Action(type=action_type, params=action_dict))
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse actions JSON: {e}")

        response_without_actions = response[: actions_match.start()].strip()
    else:
        response_without_actions = response.strip()

    # Extract stream section
    stream_match = re.search(
        r"\[STREAM\]\s*(.*)", response_without_actions, re.DOTALL | re.IGNORECASE
    )
    if stream_match:
        stream = stream_match.group(1).strip()
    else:
        stream = response_without_actions

    return PsycheResponse(stream=stream, actions=actions, raw=response)


def _remove_json_blocks(text: str) -> str:
    """Remove any JSON-like blocks from text, preserving component labels."""
    lines = []
    in_json = False
    brace_count = 0

    # Pattern for psyche component labels - these should NOT be removed
    component_pattern = re.compile(r"^\[(SHADOW|ANIMA|ANIMUS|PERSONA|SELF|STREAM|ACTIONS)\]", re.IGNORECASE)

    for line in text.split("\n"):
        stripped = line.strip()

        # Always keep component labels
        if component_pattern.match(stripped):
            lines.append(line)
            continue

        # Detect start of JSON (only { not [ which could be component label)
        if stripped.startswith("{"):
            in_json = True
            brace_count = stripped.count("{") - stripped.count("}")
            continue

        if in_json:
            brace_count += stripped.count("{") - stripped.count("}")
            if brace_count <= 0:
                in_json = False
            continue

        # Skip lines that look like JSON properties ("key": value)
        if re.match(r'^[\s]*"[^"]+"\s*:', stripped):
            continue

        lines.append(line)

    return "\n".join(lines).strip()


def _clean_json(json_str: str) -> str:
    """Clean up potentially malformed JSON from LLM output."""
    # Remove trailing commas before } or ]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    # Ensure proper quoting of keys
    # This is a simplified fix; complex cases might need more handling
    json_str = re.sub(r"(\{|,)\s*(\w+)\s*:", r'\1"\2":', json_str)

    return json_str


def extract_structured_components(stream: str) -> dict[str, list[str]]:
    """Extract labeled components from structured mode output."""
    components: dict[str, list[str]] = {
        "SHADOW": [],
        "ANIMA": [],
        "PERSONA": [],
        "SELF": [],
    }

    current_component: str | None = None
    current_text: list[str] = []

    for line in stream.split("\n"):
        # Check for component label
        label_match = re.match(r"\[(SHADOW|ANIMA|PERSONA|SELF)\](.*)$", line, re.IGNORECASE)
        if label_match:
            # Save previous component's text
            if current_component and current_text:
                components[current_component].append(" ".join(current_text).strip())
                current_text = []

            current_component = label_match.group(1).upper()
            rest = label_match.group(2).strip()
            if rest:
                current_text.append(rest)
        elif current_component:
            current_text.append(line)

    # Save last component
    if current_component and current_text:
        components[current_component].append(" ".join(current_text).strip())

    return components
