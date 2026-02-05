"""Parse responses from the psyche."""

import json
import re

from jung_agent.types import Action, PsycheResponse, StreamSegment


def parse_response(response: str) -> PsycheResponse:
    """Parse the psyche's JSON response into stream segments and actions."""
    stream: list[StreamSegment] = []
    actions: list[Action] = []

    # Find JSON object in response
    json_match = re.search(r"\{[\s\S]*\}", response)
    if not json_match:
        return PsycheResponse(stream=[], actions=[], raw=response)

    try:
        data = json.loads(json_match.group())

        # Extract stream segments
        for item in data.get("stream", []):
            component = item.get("component", "default").lower()
            text = item.get("text", "").strip()
            if text:
                stream.append(StreamSegment(component=component, text=text))

        # Extract actions
        for action_dict in data.get("actions", []):
            action_dict = dict(action_dict)  # Copy to avoid mutation
            action_type = action_dict.pop("type", None)
            if action_type:
                actions.append(Action(type=action_type, params=action_dict))

    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON: {e}")

    return PsycheResponse(stream=stream, actions=actions, raw=response)
