"""Goal types for goal-directed behavior."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GoalStatus(Enum):
    """Status of a goal in its lifecycle."""

    PENDING = "pending"  # Generated, not yet active
    ACTIVE = "active"  # Currently being pursued
    COMPLETED = "completed"  # Successfully achieved
    FAILED = "failed"  # Could not achieve
    ABANDONED = "abandoned"  # Gave up (timeout, priority shift)


@dataclass
class Goal:
    """Represents an agent goal.

    Goals are generated when drives fall below threshold. Archetypes propose
    goals, and Ego selects which to pursue based on priority and feasibility.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier"""

    description: str = ""
    """Natural language goal description"""

    related_drive: str = ""
    """Which drive triggered this goal (affiliation, nurturing, individuation)"""

    priority: float = 0.5
    """Priority (0.0-1.0) based on archetypal consensus"""

    success_criteria: dict[str, Any] = field(default_factory=dict)
    """Conditions for goal completion"""

    created_at: float = field(default_factory=time.time)
    """Timestamp when goal was created"""

    status: GoalStatus = GoalStatus.PENDING
    """Current status"""

    proposing_archetype: str = ""
    """Which archetype suggested this goal"""

    plan: Any = None  # Will be ActionPlan when planning implemented
    """Associated action plan"""

    started_at: float | None = None
    """Timestamp when goal became active"""

    completed_at: float | None = None
    """Timestamp when goal completed/failed/abandoned"""

    def activate(self) -> None:
        """Mark goal as active."""
        self.status = GoalStatus.ACTIVE
        self.started_at = time.time()

    def complete(self, success: bool = True) -> None:
        """Mark goal as completed or failed.

        Args:
            success: True if goal succeeded, False if failed
        """
        self.status = GoalStatus.COMPLETED if success else GoalStatus.FAILED
        self.completed_at = time.time()

    def abandon(self) -> None:
        """Mark goal as abandoned."""
        self.status = GoalStatus.ABANDONED
        self.completed_at = time.time()

    def is_active(self) -> bool:
        """Check if goal is currently active.

        Returns:
            True if status is ACTIVE
        """
        return self.status == GoalStatus.ACTIVE

    def is_complete(self) -> bool:
        """Check if goal is in a terminal state.

        Returns:
            True if completed, failed, or abandoned
        """
        return self.status in (
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.ABANDONED,
        )

    def get_elapsed_time(self) -> float:
        """Get time elapsed since goal became active.

        Returns:
            Seconds elapsed, or 0 if not active
        """
        if self.started_at is None:
            return 0.0

        if self.completed_at:
            return self.completed_at - self.started_at

        return time.time() - self.started_at

    def check_timeout(self) -> bool:
        """Check if goal has exceeded timeout.

        Returns:
            True if timed out
        """
        timeout = self.success_criteria.get("timeout")
        if timeout is None:
            return False

        return self.get_elapsed_time() > timeout

    def to_dict(self) -> dict[str, Any]:
        """Convert goal to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "description": self.description,
            "related_drive": self.related_drive,
            "priority": self.priority,
            "success_criteria": self.success_criteria,
            "created_at": self.created_at,
            "status": self.status.value,
            "proposing_archetype": self.proposing_archetype,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_time": self.get_elapsed_time(),
        }
