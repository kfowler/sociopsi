"""Action executor - executes plans with monitoring."""

from sociopsi.actions.registry import ActionRegistry
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.goals.goal import Goal
from sociopsi.subsystems.goals.manager import GoalManager
from sociopsi.subsystems.planning.planner import ActionPlanner


class ActionExecutor:
    """Executes action plans with monitoring and adaptation."""

    def __init__(
        self,
        event_bus: EventBus,
        action_registry: ActionRegistry,
        goal_manager: GoalManager,
        planner: ActionPlanner,
    ) -> None:
        """Initialize executor.

        Args:
            event_bus: Event bus
            action_registry: Action registry
            goal_manager: Goal manager
            planner: Action planner
        """
        self.event_bus = event_bus
        self.action_registry = action_registry
        self.goal_manager = goal_manager
        self.planner = planner
        self.executing_actions: dict[str, str] = {}  # action_name -> goal_id

    async def update(self, dt: float) -> None:
        """Update executor - execute active goal plans.

        Args:
            dt: Delta time
        """
        active_goals = self.goal_manager.get_active_goals()

        for goal in active_goals:
            # Check if goal already achieved (early termination)
            if self.goal_manager.check_success_criteria(goal):
                self.goal_manager.complete_goal(goal.id, success=True)
                continue

            # Ensure goal has a plan
            if not goal.plan:
                goal.plan = await self.planner.create_plan(goal)
                if not goal.plan:
                    self.goal_manager.abandon_goal(goal.id)
                    continue

            # Execute next step if plan not complete
            if not goal.plan.is_complete():
                await self._execute_step(goal)

            # Check timeout
            if goal.check_timeout():
                self.goal_manager.abandon_goal(goal.id)

    async def _execute_step(self, goal: Goal) -> None:
        """Execute current step of goal's plan.

        Args:
            goal: Goal with plan
        """
        if not goal.plan:
            return

        step = goal.plan.get_current_step()
        if not step:
            return

        # Check for conflicts
        if self._has_conflict(step.action_name, goal):
            return  # Wait for conflict to clear

        # Get action
        action_def = self.action_registry.get_action(step.action_name)
        if not action_def or not action_def.execute:
            # Action not available, skip step
            goal.plan.advance()
            return

        try:
            # Mark action as executing
            self.executing_actions[step.action_name] = goal.id

            # Publish step started
            self.event_bus.publish(
                "plan.step_started",
                {
                    "goal_id": goal.id,
                    "step_index": goal.plan.current_step,
                    "action_name": step.action_name,
                },
            )

            # Execute action
            await action_def.execute(**step.parameters)

            # Publish step completed
            self.event_bus.publish(
                "plan.step_completed",
                {
                    "goal_id": goal.id,
                    "step_index": goal.plan.current_step,
                    "action_name": step.action_name,
                },
            )

            # Advance to next step
            goal.plan.advance()

            # Clear executing
            if step.action_name in self.executing_actions:
                del self.executing_actions[step.action_name]

            # If plan complete, check success
            if goal.plan.is_complete():
                if self.goal_manager.check_success_criteria(goal):
                    self.goal_manager.complete_goal(goal.id, success=True)
                else:
                    self.goal_manager.complete_goal(goal.id, success=False)

        except Exception as e:
            print(f"Warning: Action {step.action_name} failed: {e}")
            # Clear executing
            if step.action_name in self.executing_actions:
                del self.executing_actions[step.action_name]
            # For now, just advance past failed step
            goal.plan.advance()

    def _has_conflict(self, action_name: str, goal: Goal) -> bool:
        """Check if action conflicts with currently executing actions.

        Args:
            action_name: Action to check
            goal: Goal requesting action

        Returns:
            True if conflicts
        """
        # Check if same action already executing
        if action_name in self.executing_actions:
            executing_goal_id = self.executing_actions[action_name]
            # Allow if same goal, block if different goal
            return executing_goal_id != goal.id

        # Check registry conflicts
        for executing_action in self.executing_actions.keys():
            if self.action_registry.check_conflict(action_name, executing_action):
                return True

        return False
