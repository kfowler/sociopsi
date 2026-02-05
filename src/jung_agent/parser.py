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

    # Find JSON object in response
    json_match = re.search(r"\{[\s\S]*\}", response)
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

        for item in stream_data:
            # Handle malformed stream items
            if isinstance(item, str):
                # LLM returned a string instead of object
                if item.strip():
                    stream.append(StreamSegment(component="default", text=item.strip()))
                continue
            if not isinstance(item, dict):
                continue
            component = item.get("component", "default")
            if not isinstance(component, str):
                component = "default"
            text = item.get("text", "")
            if not isinstance(text, str):
                text = str(text) if text else ""
            text = text.strip()
            if text:
                stream.append(StreamSegment(component=component.lower(), text=text))

        # Extract actions
        for action_dict in data.get("actions", []):
            if not isinstance(action_dict, dict):
                continue
            action_dict = dict(action_dict)  # Copy to avoid mutation
            action_type = action_dict.pop("type", None)
            if action_type and isinstance(action_type, str):
                actions.append(Action(type=action_type, params=action_dict))

    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON: {e}")
        _log_json_error(response, json_str, e)

    return PsycheResponse(stream=stream, actions=actions, raw=response)


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
