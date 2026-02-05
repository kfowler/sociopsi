"""Parse responses from the psyche."""

import json
import re
from datetime import datetime
from pathlib import Path

from jung_agent.types import Action, PsycheResponse, StreamSegment

# Log directory for JSON errors
_ERROR_LOG_DIR = Path.home() / ".jung" / "logs" / "json_errors"
_ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)


def parse_response(response: str) -> PsycheResponse:
    """Parse the psyche's JSON response into stream segments and actions."""
    stream: list[StreamSegment] = []
    actions: list[Action] = []

    # Strip markdown code blocks first
    clean_response = response
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if code_block_match:
        clean_response = code_block_match.group(1)

    # Find JSON object in response
    json_match = re.search(r"\{[\s\S]*\}", clean_response)
    if not json_match:
        return PsycheResponse(stream=[], actions=[], raw=response)

    json_str = json_match.group()

    # Try to repair common JSON issues
    json_str = _repair_json(json_str)

    try:
        data = json.loads(json_str)

        # Extract stream segments
        stream_data = data.get("stream", [])

        # Handle stream as a single string
        if isinstance(stream_data, str):
            if stream_data.strip():
                stream.append(StreamSegment(component="default", text=stream_data.strip()))
            stream_data = []  # Don't iterate

        # Handle stream as an object (wrong format but try to extract)
        if isinstance(stream_data, dict):
            for key, value in stream_data.items():
                comp = _normalize_component(key)
                text = _extract_text(value)
                if text:
                    stream.append(StreamSegment(component=comp, text=text))
            stream_data = []  # Don't iterate further

        for item in stream_data:
            # Handle malformed stream items
            if isinstance(item, str):
                # LLM returned a string instead of object
                if item.strip():
                    stream.append(StreamSegment(component="default", text=item.strip()))
                continue
            if not isinstance(item, dict):
                continue

            # Check if this is a multi-component item like {"persona": "...", "shadow": "..."}
            component_keys = [k for k in item.keys() if _normalize_component(k) != "default"]
            if component_keys and "component" not in item and "text" not in item:
                # Multi-component format: extract each
                for key in component_keys:
                    comp = _normalize_component(key)
                    text = _extract_text(item[key])
                    if text:
                        stream.append(StreamSegment(component=comp, text=text))
            else:
                # Standard format: {"component": "...", "text": "..."}
                component = _extract_component(item)
                text = _extract_text(item)
                if text:
                    stream.append(StreamSegment(component=component, text=text))

        # Extract actions
        for action_dict in data.get("actions", []):
            if not isinstance(action_dict, dict):
                continue
            action_dict = dict(action_dict)  # Copy to avoid mutation
            # Try "type" first, then "action" as fallback
            action_type = action_dict.pop("type", None) or action_dict.pop("action", None)
            if action_type and isinstance(action_type, str):
                actions.append(Action(type=action_type, params=action_dict))

    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON: {e}")
        _log_json_error(response, json_str, e)

    return PsycheResponse(stream=stream, actions=actions, raw=response)


def _normalize_component(name: str) -> str:
    """Normalize component name to standard form."""
    name_lower = name.lower()
    # Map various names to standard components
    if "shadow" in name_lower:
        return "shadow"
    if "anima" in name_lower or "animus" in name_lower:
        return "anima"
    if "persona" in name_lower:
        return "persona"
    if "self" in name_lower:
        return "self"
    return "default"


def _extract_component(item: dict) -> str:
    """Extract component name from a stream item dict."""
    # Standard format: {"component": "shadow", "text": "..."}
    if "component" in item:
        comp = item["component"]
        if isinstance(comp, str):
            return _normalize_component(comp)

    # Alternate format: {"persona": "...", ...} or {"shadow": "...", ...}
    for key in ["shadow", "anima", "animus", "persona", "self"]:
        if key in item:
            return _normalize_component(key)

    # Check if any key name looks like a component
    for key in item.keys():
        normalized = _normalize_component(key)
        if normalized != "default":
            return normalized

    return "default"


def _extract_text(item: dict | list | str) -> str:
    """Extract text content from various formats."""
    if isinstance(item, str):
        return item.strip()

    if isinstance(item, list):
        # Join list items
        texts = [_extract_text(x) for x in item]
        return " ".join(t for t in texts if t)

    if not isinstance(item, dict):
        return str(item) if item else ""

    # Try various text keys
    text_keys = ["text", "voice", "expression", "content", "message", "dialogue"]
    for key in text_keys:
        if key in item and item[key]:
            val = item[key]
            if isinstance(val, str):
                return val.strip()
            return str(val).strip()

    # If there's only one string value in the dict, use it
    string_values = [v for v in item.values() if isinstance(v, str) and v.strip()]
    if len(string_values) == 1:
        return string_values[0].strip()

    return ""


def _repair_json(json_str: str) -> str:
    """Attempt to repair common JSON issues from LLM output."""
    # Remove any trailing commas before } or ]
    json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

    # Fix missing colon after "actions" (seen in logs: "actions [" instead of "actions": [)
    json_str = re.sub(r'"actions"\s*\[', '"actions": [', json_str)
    json_str = re.sub(r'"stream"\s*\[', '"stream": [', json_str)

    # Fix single quotes used as string delimiters (only if no double quotes present)
    if '"' not in json_str and "'" in json_str:
        json_str = json_str.replace("'", '"')

    # Replace [...] placeholder with empty array
    json_str = re.sub(r"\[\s*\.\.\.\s*\]", "[]", json_str)

    # Replace {...} placeholder with empty object
    json_str = re.sub(r"\{\s*\.\.\.\s*\}", "{}", json_str)

    # Remove any text after the final } (use rfind to get last occurrence)
    last_brace = json_str.rfind("}")
    if last_brace != -1:
        json_str = json_str[: last_brace + 1]

    return json_str


def _log_json_error(raw_response: str, json_str: str, error: json.JSONDecodeError) -> None:
    """Log JSON parsing errors for debugging."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    error_file = _ERROR_LOG_DIR / f"error_{timestamp}.txt"

    with open(error_file, "w") as f:
        f.write(f"Error: {error}\n")
        f.write(f"Position: line {error.lineno}, column {error.colno}, char {error.pos}\n")
        f.write("-" * 60 + "\n")
        f.write("Raw response (before extraction):\n")
        f.write(raw_response)
        f.write("\n" + "-" * 60 + "\n")
        f.write("JSON string (after extraction and repair):\n")
        f.write(json_str)
        f.write("\n" + "-" * 60 + "\n")

        # Try to show context around the error in the JSON string
        if error.pos < len(json_str):
            start = max(0, error.pos - 50)
            end = min(len(json_str), error.pos + 50)
            f.write(f"Context around error (char {error.pos}):\n")
            f.write(json_str[start : error.pos] + " <<ERROR>> " + json_str[error.pos : end])
            f.write("\n")

    print(f"  JSON error logged to: {error_file}")
