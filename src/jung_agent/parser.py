"""Parse responses from the psyche."""

import json
import re

from jung_agent.types import Action, PsycheResponse


def parse_response(response: str) -> PsycheResponse:
    """Parse the psyche's response into stream and actions."""
    stream = ""
    actions: list[Action] = []

    # Extract stream section
    stream_match = re.search(
        r"\[STREAM\](.*?)(?=\[ACTIONS\]|$)", response, re.DOTALL | re.IGNORECASE
    )
    if stream_match:
        stream = stream_match.group(1).strip()
    else:
        # If no [STREAM] tag, treat everything before [ACTIONS] as stream
        actions_start = response.lower().find("[actions]")
        if actions_start > 0:
            stream = response[:actions_start].strip()
        else:
            stream = response.strip()

    # Extract actions section
    actions_match = re.search(
        r"\[ACTIONS\]\s*(\{.*\})", response, re.DOTALL | re.IGNORECASE
    )
    if actions_match:
        try:
            actions_json = actions_match.group(1)
            # Clean up potential issues
            actions_json = _clean_json(actions_json)
            actions_data = json.loads(actions_json)

            for action_dict in actions_data.get("actions", []):
                action_type = action_dict.pop("type", None)
                if action_type:
                    actions.append(Action(type=action_type, params=action_dict))
        except json.JSONDecodeError as e:
            # Log but don't fail
            print(f"Warning: Could not parse actions JSON: {e}")

    return PsycheResponse(stream=stream, actions=actions, raw=response)


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
