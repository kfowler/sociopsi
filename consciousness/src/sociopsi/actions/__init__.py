"""Action system for goal-directed behavior."""

from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import ActionRegistry, get_registry
from sociopsi.actions.speak import SpeechAction

__all__ = [
    "ActionDefinition",
    "ActionRegistry",
    "get_registry",
    "SpeechAction",
]
