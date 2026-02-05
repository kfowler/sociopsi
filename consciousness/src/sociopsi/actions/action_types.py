"""Action type definitions."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionDefinition:
    """Metadata and execution handler for an action.

    Actions are the primitive behaviors the agent can perform to achieve goals.
    Each action has a name, description (for LLM planning), parameter schema,
    conflict rules, and an async execution function.
    """

    name: str
    """Unique action name (e.g., 'speak', 'wait')"""

    description: str
    """Human-readable description for LLM planning prompts"""

    parameters: dict[str, Any]
    """JSON schema for action parameters"""

    conflicts_with: list[str] = field(default_factory=list)
    """List of action names this action conflicts with"""

    estimated_duration: float = 1.0
    """Typical duration in seconds (for planning)"""

    execute: Callable[..., Awaitable[None]] | None = None
    """Async function to execute the action"""

    def get_param_schema_summary(self) -> str:
        """Get a summary of parameters for LLM prompts.

        Returns:
            String like "text (required), emotion (optional)"
        """
        params = []
        for name, schema in self.parameters.items():
            required = schema.get("required", False)
            param_type = schema.get("type", "any")
            qualifier = "required" if required else "optional"
            params.append(f"{name}: {param_type} ({qualifier})")
        return ", ".join(params) if params else "no parameters"

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate provided parameters against schema.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for name, schema in self.parameters.items():
            if schema.get("required", False) and name not in params:
                return False, f"Missing required parameter: {name}"

        # Check parameter types (basic validation)
        for name, value in params.items():
            if name not in self.parameters:
                return False, f"Unknown parameter: {name}"

            expected_type = self.parameters[name].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return False, f"Parameter {name} must be a string"
            elif expected_type == "number" and not isinstance(value, (int, float)):
                return False, f"Parameter {name} must be a number"
            elif expected_type == "boolean" and not isinstance(value, bool):
                return False, f"Parameter {name} must be a boolean"

        return True, None
