"""Action plan types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionStep:
    """Single step in an action plan."""

    action_name: str
    """Name of action to execute (must be in action registry)"""

    parameters: dict[str, Any]
    """Parameters for the action"""

    optional: bool = False
    """Whether this step can be skipped if blocking"""

    timeout: float | None = None
    """Maximum time for this step (seconds)"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "action_name": self.action_name,
            "parameters": self.parameters,
            "optional": self.optional,
            "timeout": self.timeout,
        }


@dataclass
class ActionPlan:
    """A sequence of actions to achieve a goal."""

    goal_id: str
    """ID of associated goal"""

    steps: list[ActionStep] = field(default_factory=list)
    """Ordered action steps"""

    created_at: float = 0.0
    """When plan was created"""

    current_step: int = 0
    """Index of current step being executed"""

    def get_current_step(self) -> ActionStep | None:
        """Get current step to execute.

        Returns:
            Current step or None if plan complete
        """
        if self.current_step >= len(self.steps):
            return None
        return self.steps[self.current_step]

    def advance(self) -> None:
        """Advance to next step."""
        self.current_step += 1

    def is_complete(self) -> bool:
        """Check if all steps executed.

        Returns:
            True if no more steps
        """
        return self.current_step >= len(self.steps)

    def get_remaining_steps(self) -> list[ActionStep]:
        """Get list of remaining steps.

        Returns:
            Steps not yet executed
        """
        return self.steps[self.current_step :]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "goal_id": self.goal_id,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "current_step": self.current_step,
            "total_steps": len(self.steps),
            "is_complete": self.is_complete(),
        }
