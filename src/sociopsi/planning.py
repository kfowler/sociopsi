"""Hierarchical planning system inspired by MicroPsi2's ReCoN scripts.

Provides goal management and plan generation for the Socio-Psi agent.
Goals are derived from drive urgencies. When a goal activates, the LLM
decomposes it into a sequence of actions (a Plan). The plan is executed
step-by-step, with re-planning on failure.

This is a single-level implementation (no subgoal decomposition).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sociopsi.types import Action, ActionResult

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    """Status of a goal in the goal stack."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ACHIEVED = "achieved"
    FAILED = "failed"


@dataclass
class Goal:
    """A goal derived from a drive urgency.

    Attributes:
        drive_name: The drive that spawned this goal.
        target_demand: Target demand level for the drive (lower = more satisfied).
        priority: Priority derived from drive urgency at creation time.
        status: Current goal status.
        created_at: Timestamp when the goal was created.
        attempts: Number of times we've tried to plan for this goal.
        max_attempts: Maximum re-plan attempts before failing the goal.
    """

    drive_name: str
    target_demand: float = 0.3
    priority: float = 0.0
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class PlanStep:
    """A single step in a plan.

    Attributes:
        action: The action to execute.
        completed: Whether this step has been executed.
        result: The result of execution, if completed.
    """

    action: Action
    completed: bool = False
    result: ActionResult | None = None


@dataclass
class Plan:
    """A sequence of actions toward achieving a goal.

    Attributes:
        goal: The goal this plan serves.
        steps: Ordered list of plan steps.
        current_step: Index of the next step to execute.
        created_at: Timestamp when the plan was created.
    """

    goal: Goal
    steps: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def is_complete(self) -> bool:
        """Whether all steps have been executed."""
        return self.current_step >= len(self.steps)

    @property
    def is_empty(self) -> bool:
        """Whether the plan has no steps."""
        return len(self.steps) == 0

    def next_action(self) -> Action | None:
        """Get the next action to execute, or None if plan is complete."""
        if self.is_complete:
            return None
        return self.steps[self.current_step].action

    def record_result(self, result: ActionResult) -> None:
        """Record the result of executing the current step."""
        if not self.is_complete:
            self.steps[self.current_step].completed = True
            self.steps[self.current_step].result = result
            self.current_step += 1


# Drive-to-goal urgency threshold: goals are created when urgency exceeds this.
GOAL_URGENCY_THRESHOLD = 0.6

# How long a goal stays relevant before being considered stale (seconds).
GOAL_STALENESS_TIMEOUT = 120.0

# Available actions the planner can choose from, grouped by drive affinity.
# The planner uses these as its vocabulary when generating plans.
DRIVE_ACTION_VOCABULARY: dict[str, list[str]] = {
    "energy": ["check_battery", "set_power_mode", "sleep"],
    "integrity": ["check_thermals", "check_memory", "close_app", "meditate"],
    "arousal": ["look", "listen", "check_time", "stretch", "play_piano"],
    "competence": ["compose_thought", "journal_write", "web_search", "open_app"],
    "certainty": ["sense_all", "check_time", "check_calendar", "recall_memory"],
    "curiosity": ["look", "observe", "web_search", "read_hacker_news", "dream"],
    "affiliation": ["look", "listen", "speak", "sense_presence", "scan_local"],
    "recognition": ["notify", "speak", "compose_thought", "display_message"],
    "individuation": ["journal_write", "compose_thought", "meditate", "dream"],
}


def build_plan_prompt(
    goal: Goal,
    drive_states: dict[str, dict[str, Any]],
    available_actions: list[str],
    recent_results: list[ActionResult],
) -> str:
    """Build a prompt for the LLM to generate a plan.

    Args:
        goal: The goal to plan for.
        drive_states: Current drive state dictionary.
        available_actions: Actions the planner can use.
        recent_results: Recent action results for context.

    Returns:
        A prompt string for the LLM.
    """
    # Format drive context
    drive_lines = []
    for name, state in drive_states.items():
        drive_lines.append(f"  {name}: demand={state['value']:.2f}")

    # Format available actions
    actions_str = ", ".join(available_actions)

    # Format recent results for context
    result_lines = []
    for r in recent_results[-3:]:
        status = "success" if r.success else f"failed: {r.error}"
        result_lines.append(f"  {r.action_type}: {status}")

    recent_context = ""
    if result_lines:
        recent_context = "\nRecent results:\n" + "\n".join(result_lines)

    attempt_note = ""
    if goal.attempts > 0:
        attempt_note = (
            f"\nThis is re-plan attempt {goal.attempts + 1}. "
            "Previous plan failed. Try a different approach."
        )

    return f"""You are planning actions for a drive-based agent.

Goal: Reduce the "{goal.drive_name}" drive demand (currently high).
Target: Lower demand toward {goal.target_demand:.1f}.
{attempt_note}
Current drives:
{chr(10).join(drive_lines)}
{recent_context}
Available actions: {actions_str}

Output 1-3 actions as a JSON array. Each action is {{"type": "<action_name>"}}.
Pick actions that will satisfy the "{goal.drive_name}" drive.
Output ONLY the JSON array, nothing else.

Example: [{{"type": "look"}}, {{"type": "speak"}}]"""


def parse_plan_response(response: str, available_actions: list[str]) -> list[Action]:
    """Parse the LLM's plan response into a list of actions.

    Args:
        response: Raw LLM response text.
        available_actions: Valid action types to filter against.

    Returns:
        List of valid actions extracted from the response.
    """
    import json

    actions: list[Action] = []

    # Try to extract a JSON array from the response
    text = response.strip()

    # Find the first [ and last ] to extract array
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning(f"No JSON array found in plan response: {text[:100]}")
        return actions

    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse plan JSON: {text[start:end + 1][:100]}")
        return actions

    if not isinstance(items, list):
        return actions

    for item in items:
        if isinstance(item, dict) and "type" in item:
            action_type = item["type"]
            if action_type in available_actions:
                params = {k: v for k, v in item.items() if k != "type"}
                actions.append(Action(type=action_type, params=params))
            else:
                logger.debug(f"Planner proposed unknown action: {action_type}")

    return actions


class GoalStack:
    """Manages the goal stack and active plans.

    The goal stack is an ordered list of goals derived from drive urgencies.
    Each goal can have at most one active plan. Goals are created when drives
    cross an urgency threshold, and removed when achieved or failed.
    """

    def __init__(self) -> None:
        self._goals: list[Goal] = []
        self._plans: dict[str, Plan] = {}  # drive_name -> active plan

    @property
    def goals(self) -> list[Goal]:
        """All goals, sorted by priority (highest first)."""
        return sorted(
            [g for g in self._goals if g.status == GoalStatus.ACTIVE],
            key=lambda g: -g.priority,
        )

    @property
    def active_plan(self) -> Plan | None:
        """The plan for the highest-priority active goal, if any."""
        for goal in self.goals:
            if goal.drive_name in self._plans:
                plan = self._plans[goal.drive_name]
                if not plan.is_complete:
                    return plan
        return None

    def update_from_drives(self, drive_states: dict[str, dict[str, Any]]) -> list[Goal]:
        """Create or update goals based on current drive urgencies.

        Args:
            drive_states: Dict mapping drive names to their state dicts.
                Each state dict should have "value" (demand) and optionally
                "urgency" keys.

        Returns:
            List of newly created goals.
        """
        new_goals: list[Goal] = []
        now = time.time()

        # Remove stale or resolved goals
        self._goals = [
            g
            for g in self._goals
            if g.status == GoalStatus.ACTIVE
            and (now - g.created_at) < GOAL_STALENESS_TIMEOUT
        ]

        # Check which drives need new goals
        active_drive_names = {g.drive_name for g in self._goals if g.status == GoalStatus.ACTIVE}

        for drive_name, state in drive_states.items():
            demand = state.get("value", 0.0)
            urgency = state.get("urgency", demand)

            if urgency >= GOAL_URGENCY_THRESHOLD and drive_name not in active_drive_names:
                goal = Goal(
                    drive_name=drive_name,
                    target_demand=0.3,
                    priority=urgency,
                )
                self._goals.append(goal)
                new_goals.append(goal)
                logger.info(f"New goal: reduce {drive_name} (urgency={urgency:.2f})")

            # Update priority for existing goals
            for goal in self._goals:
                if goal.drive_name == drive_name and goal.status == GoalStatus.ACTIVE:
                    goal.priority = urgency

        return new_goals

    def create_plan(self, goal: Goal, actions: list[Action]) -> Plan:
        """Create a new plan for a goal.

        Args:
            goal: The goal to create a plan for.
            actions: The sequence of actions for the plan.

        Returns:
            The newly created plan.
        """
        plan = Plan(
            goal=goal,
            steps=[PlanStep(action=a) for a in actions],
        )
        self._plans[goal.drive_name] = plan
        goal.attempts += 1
        logger.info(
            f"Plan for {goal.drive_name}: {[a.type for a in actions]} "
            f"(attempt {goal.attempts})"
        )
        return plan

    def mark_goal_achieved(self, drive_name: str) -> None:
        """Mark a goal as achieved and clean up its plan.

        Args:
            drive_name: The drive name of the goal to mark as achieved.
        """
        for goal in self._goals:
            if goal.drive_name == drive_name and goal.status == GoalStatus.ACTIVE:
                goal.status = GoalStatus.ACHIEVED
                logger.info(f"Goal achieved: {drive_name}")
        self._plans.pop(drive_name, None)

    def mark_goal_failed(self, drive_name: str) -> None:
        """Mark a goal as failed and clean up its plan.

        Args:
            drive_name: The drive name of the goal to mark as failed.
        """
        for goal in self._goals:
            if goal.drive_name == drive_name and goal.status == GoalStatus.ACTIVE:
                goal.status = GoalStatus.FAILED
                logger.info(f"Goal failed: {drive_name}")
        self._plans.pop(drive_name, None)

    def needs_plan(self, goal: Goal) -> bool:
        """Check whether a goal needs a new plan.

        Args:
            goal: The goal to check.

        Returns:
            True if the goal has no active plan or its plan is complete/empty.
        """
        if goal.drive_name not in self._plans:
            return True
        plan = self._plans[goal.drive_name]
        return plan.is_complete or plan.is_empty

    def handle_step_failure(self, plan: Plan) -> bool:
        """Handle a failed plan step by deciding whether to re-plan.

        Args:
            plan: The plan with a failed step.

        Returns:
            True if re-planning should be attempted, False if the goal
            should be marked as failed.
        """
        goal = plan.goal
        if goal.attempts >= goal.max_attempts:
            self.mark_goal_failed(goal.drive_name)
            return False

        # Clear the current plan to trigger re-planning
        self._plans.pop(goal.drive_name, None)
        logger.info(
            f"Plan step failed for {goal.drive_name}, will re-plan "
            f"(attempt {goal.attempts}/{goal.max_attempts})"
        )
        return True

    def get_next_actions(self) -> list[Action]:
        """Get the next actions from the highest-priority active plan.

        Returns:
            A list containing the next action (0-1 items), or empty if
            no active plans have pending steps.
        """
        plan = self.active_plan
        if plan is None:
            return []

        action = plan.next_action()
        if action is None:
            return []

        return [action]

    def record_result(self, plan: Plan, result: ActionResult) -> None:
        """Record an action result and check goal progress.

        Args:
            plan: The plan whose step was executed.
            result: The result of the execution.
        """
        plan.record_result(result)

        if not result.success:
            self.handle_step_failure(plan)

    def check_goal_satisfaction(self, drive_states: dict[str, dict[str, Any]]) -> None:
        """Check if any active goals have been satisfied by drive changes.

        Args:
            drive_states: Current drive state dictionary.
        """
        for goal in list(self._goals):
            if goal.status != GoalStatus.ACTIVE:
                continue
            state = drive_states.get(goal.drive_name)
            if state is None:
                continue
            demand = state.get("value", 1.0)
            if demand <= goal.target_demand:
                self.mark_goal_achieved(goal.drive_name)

    def format_for_perception(self) -> str:
        """Format the goal stack and plans for inclusion in perception.

        Returns:
            A string describing active goals and plans, or empty string
            if no active goals.
        """
        active = self.goals
        if not active:
            return ""

        lines = ["[GOALS]"]
        for goal in active:
            plan = self._plans.get(goal.drive_name)
            if plan and not plan.is_complete:
                step_info = f"step {plan.current_step + 1}/{len(plan.steps)}"
                next_action = plan.next_action()
                action_str = f" -> {next_action.type}" if next_action else ""
                lines.append(
                    f"  {goal.drive_name} (p={goal.priority:.2f}): "
                    f"{step_info}{action_str}"
                )
            else:
                lines.append(f"  {goal.drive_name} (p={goal.priority:.2f}): needs plan")

        return "\n".join(lines)
