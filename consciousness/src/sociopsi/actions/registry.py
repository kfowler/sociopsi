"""Action registry for managing available actions."""

from sociopsi.actions.action_types import ActionDefinition


class ActionRegistry:
    """Central registry of available actions.

    The registry manages all actions the agent can perform. Actions register
    themselves at startup, and the registry provides lookup and enumeration
    for planning and execution.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self.actions: dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition) -> None:
        """Register an action.

        Args:
            action: Action definition to register

        Raises:
            ValueError: If action with same name already registered
        """
        if action.name in self.actions:
            raise ValueError(f"Action '{action.name}' is already registered")

        self.actions[action.name] = action

    def get_action(self, name: str) -> ActionDefinition | None:
        """Get action by name.

        Args:
            name: Action name

        Returns:
            Action definition or None if not found
        """
        return self.actions.get(name)

    def has_action(self, name: str) -> bool:
        """Check if action exists.

        Args:
            name: Action name

        Returns:
            True if action registered
        """
        return name in self.actions

    def get_all_actions(self) -> list[ActionDefinition]:
        """Get all registered actions.

        Returns:
            List of action definitions
        """
        return list(self.actions.values())

    def get_actions_summary(self) -> str:
        """Get summary of all actions for LLM prompts.

        Returns:
            String describing all available actions
        """
        if not self.actions:
            return "No actions available"

        lines = ["Available actions:"]
        for action in self.actions.values():
            params = action.get_param_schema_summary()
            duration = f"~{action.estimated_duration}s"
            lines.append(f"- {action.name}: {action.description} ({params}) [{duration}]")

        return "\n".join(lines)

    def check_conflict(self, action1: str, action2: str) -> bool:
        """Check if two actions conflict.

        Args:
            action1: First action name
            action2: Second action name

        Returns:
            True if actions conflict
        """
        if action1 not in self.actions or action2 not in self.actions:
            return False

        # Check if action1 conflicts with action2
        if action2 in self.actions[action1].conflicts_with:
            return True

        # Check if action2 conflicts with action1
        if action1 in self.actions[action2].conflicts_with:
            return True

        return False

    def clear(self) -> None:
        """Clear all registered actions (for testing)."""
        self.actions.clear()


# Global registry instance
_registry = ActionRegistry()


def get_registry() -> ActionRegistry:
    """Get the global action registry.

    Returns:
        The global ActionRegistry instance
    """
    return _registry
