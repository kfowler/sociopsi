"""Tests for the hierarchical planning system."""

import time

import pytest

from sociopsi.planning import (
    DRIVE_ACTION_VOCABULARY,
    Goal,
    GoalStack,
    GoalStatus,
    Plan,
    PlanStep,
    build_plan_prompt,
    parse_plan_response,
)
from sociopsi.types import Action, ActionResult


class TestGoal:
    """Tests for the Goal dataclass."""

    def test_goal_defaults(self) -> None:
        goal = Goal(drive_name="curiosity")
        assert goal.drive_name == "curiosity"
        assert goal.target_demand == 0.3
        assert goal.priority == 0.0
        assert goal.status == GoalStatus.ACTIVE
        assert goal.attempts == 0
        assert goal.max_attempts == 3

    def test_goal_custom_values(self) -> None:
        goal = Goal(
            drive_name="energy",
            target_demand=0.2,
            priority=0.9,
            max_attempts=5,
        )
        assert goal.target_demand == 0.2
        assert goal.priority == 0.9
        assert goal.max_attempts == 5


class TestPlanStep:
    """Tests for the PlanStep dataclass."""

    def test_plan_step_defaults(self) -> None:
        action = Action(type="look")
        step = PlanStep(action=action)
        assert step.action.type == "look"
        assert step.completed is False
        assert step.result is None


class TestPlan:
    """Tests for the Plan dataclass."""

    def test_empty_plan(self) -> None:
        goal = Goal(drive_name="curiosity")
        plan = Plan(goal=goal)
        assert plan.is_empty
        assert plan.is_complete
        assert plan.next_action() is None

    def test_plan_with_steps(self) -> None:
        goal = Goal(drive_name="curiosity")
        steps = [
            PlanStep(action=Action(type="look")),
            PlanStep(action=Action(type="observe")),
        ]
        plan = Plan(goal=goal, steps=steps)

        assert not plan.is_empty
        assert not plan.is_complete
        assert plan.current_step == 0

        next_action = plan.next_action()
        assert next_action is not None
        assert next_action.type == "look"

    def test_plan_step_through(self) -> None:
        goal = Goal(drive_name="curiosity")
        steps = [
            PlanStep(action=Action(type="look")),
            PlanStep(action=Action(type="observe")),
        ]
        plan = Plan(goal=goal, steps=steps)

        # Execute first step
        result1 = ActionResult(action_type="look", success=True)
        plan.record_result(result1)
        assert plan.current_step == 1
        assert steps[0].completed
        assert steps[0].result == result1

        # Execute second step
        result2 = ActionResult(action_type="observe", success=True)
        plan.record_result(result2)
        assert plan.current_step == 2
        assert plan.is_complete
        assert plan.next_action() is None

    def test_plan_record_result_when_complete_is_noop(self) -> None:
        goal = Goal(drive_name="curiosity")
        plan = Plan(goal=goal, steps=[PlanStep(action=Action(type="look"))])
        plan.record_result(ActionResult(action_type="look", success=True))
        assert plan.is_complete

        # Recording another result on a complete plan is a no-op
        plan.record_result(ActionResult(action_type="observe", success=True))
        assert plan.current_step == 1  # Unchanged


class TestParsePlanResponse:
    """Tests for parse_plan_response."""

    def test_valid_json_array(self) -> None:
        response = '[{"type": "look"}, {"type": "observe"}]'
        actions = parse_plan_response(response, ["look", "observe", "speak"])
        assert len(actions) == 2
        assert actions[0].type == "look"
        assert actions[1].type == "observe"

    def test_json_with_surrounding_text(self) -> None:
        response = 'Here is the plan:\n[{"type": "speak"}]\nDone.'
        actions = parse_plan_response(response, ["speak"])
        assert len(actions) == 1
        assert actions[0].type == "speak"

    def test_filters_invalid_actions(self) -> None:
        response = '[{"type": "look"}, {"type": "fly_to_moon"}]'
        actions = parse_plan_response(response, ["look", "observe"])
        assert len(actions) == 1
        assert actions[0].type == "look"

    def test_empty_response(self) -> None:
        actions = parse_plan_response("", ["look"])
        assert actions == []

    def test_invalid_json(self) -> None:
        actions = parse_plan_response("[{broken json", ["look"])
        assert actions == []

    def test_no_array(self) -> None:
        actions = parse_plan_response('{"type": "look"}', ["look"])
        assert actions == []

    def test_preserves_extra_params(self) -> None:
        response = '[{"type": "web_search", "query": "python tips"}]'
        actions = parse_plan_response(response, ["web_search"])
        assert len(actions) == 1
        assert actions[0].type == "web_search"
        assert actions[0].params == {"query": "python tips"}

    def test_skips_non_dict_items(self) -> None:
        response = '[{"type": "look"}, "not_a_dict", 42]'
        actions = parse_plan_response(response, ["look"])
        assert len(actions) == 1


class TestGoalStack:
    """Tests for the GoalStack class."""

    @pytest.fixture
    def stack(self) -> GoalStack:
        return GoalStack()

    @pytest.fixture
    def high_urgency_drives(self) -> dict[str, dict[str, float]]:
        return {
            "curiosity": {"value": 0.8, "urgency": 0.85},
            "energy": {"value": 0.3, "urgency": 0.2},
        }

    def test_empty_stack(self, stack: GoalStack) -> None:
        assert stack.goals == []
        assert stack.active_plan is None
        assert stack.get_next_actions() == []

    def test_update_from_drives_creates_goals(
        self, stack: GoalStack, high_urgency_drives: dict[str, dict[str, float]]
    ) -> None:
        new_goals = stack.update_from_drives(high_urgency_drives)

        assert len(new_goals) == 1
        assert new_goals[0].drive_name == "curiosity"
        assert new_goals[0].priority == 0.85

    def test_no_duplicate_goals(
        self, stack: GoalStack, high_urgency_drives: dict[str, dict[str, float]]
    ) -> None:
        stack.update_from_drives(high_urgency_drives)
        new_goals = stack.update_from_drives(high_urgency_drives)
        assert len(new_goals) == 0  # No new goals

    def test_priority_update(
        self, stack: GoalStack, high_urgency_drives: dict[str, dict[str, float]]
    ) -> None:
        stack.update_from_drives(high_urgency_drives)

        # Increase urgency
        high_urgency_drives["curiosity"]["urgency"] = 0.95
        stack.update_from_drives(high_urgency_drives)

        assert stack.goals[0].priority == 0.95

    def test_goal_ordering_by_priority(self, stack: GoalStack) -> None:
        drives = {
            "curiosity": {"value": 0.7, "urgency": 0.7},
            "affiliation": {"value": 0.9, "urgency": 0.9},
        }
        stack.update_from_drives(drives)

        goals = stack.goals
        assert len(goals) == 2
        assert goals[0].drive_name == "affiliation"  # Higher priority
        assert goals[1].drive_name == "curiosity"

    def test_create_plan(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)

        actions = [Action(type="look"), Action(type="observe")]
        plan = stack.create_plan(goal, actions)

        assert len(plan.steps) == 2
        assert goal.attempts == 1
        assert stack.active_plan is plan

    def test_get_next_actions(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        stack.create_plan(goal, [Action(type="look"), Action(type="observe")])

        actions = stack.get_next_actions()
        assert len(actions) == 1
        assert actions[0].type == "look"

    def test_record_result_advances_plan(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        plan = stack.create_plan(goal, [Action(type="look"), Action(type="observe")])

        result = ActionResult(action_type="look", success=True)
        stack.record_result(plan, result)

        actions = stack.get_next_actions()
        assert len(actions) == 1
        assert actions[0].type == "observe"

    def test_record_failure_triggers_replan(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        plan = stack.create_plan(goal, [Action(type="look")])

        result = ActionResult(action_type="look", success=False, error="camera unavailable")
        stack.record_result(plan, result)

        # Plan should be cleared, goal still active
        assert goal.status == GoalStatus.ACTIVE
        assert stack.needs_plan(goal)

    def test_max_attempts_fails_goal(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8, max_attempts=2)
        stack._goals.append(goal)

        # First attempt
        plan1 = stack.create_plan(goal, [Action(type="look")])
        stack.record_result(plan1, ActionResult(action_type="look", success=False, error="fail"))

        # Second attempt
        plan2 = stack.create_plan(goal, [Action(type="observe")])
        stack.record_result(plan2, ActionResult(action_type="observe", success=False, error="fail"))

        assert goal.status == GoalStatus.FAILED

    def test_mark_goal_achieved(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        stack.create_plan(goal, [Action(type="look")])

        stack.mark_goal_achieved("curiosity")
        assert goal.status == GoalStatus.ACHIEVED
        assert "curiosity" not in stack._plans

    def test_check_goal_satisfaction(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8, target_demand=0.3)
        stack._goals.append(goal)

        # Drive demand still high
        stack.check_goal_satisfaction({"curiosity": {"value": 0.7}})
        assert goal.status == GoalStatus.ACTIVE

        # Drive demand dropped below target
        stack.check_goal_satisfaction({"curiosity": {"value": 0.2}})
        assert goal.status == GoalStatus.ACHIEVED

    def test_needs_plan(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)

        assert stack.needs_plan(goal)

        stack.create_plan(goal, [Action(type="look")])
        assert not stack.needs_plan(goal)

    def test_needs_plan_when_complete(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        plan = stack.create_plan(goal, [Action(type="look")])

        # Complete the plan
        plan.record_result(ActionResult(action_type="look", success=True))
        assert stack.needs_plan(goal)

    def test_stale_goals_removed(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        goal.created_at = time.time() - 200  # Created 200s ago
        stack._goals.append(goal)

        # Update should remove stale goal
        stack.update_from_drives({"curiosity": {"value": 0.3, "urgency": 0.3}})
        assert len(stack._goals) == 0

    def test_format_for_perception_empty(self, stack: GoalStack) -> None:
        assert stack.format_for_perception() == ""

    def test_format_for_perception_with_goals(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)

        text = stack.format_for_perception()
        assert "[GOALS]" in text
        assert "curiosity" in text
        assert "needs plan" in text

    def test_format_for_perception_with_plan(self, stack: GoalStack) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        stack._goals.append(goal)
        stack.create_plan(goal, [Action(type="look"), Action(type="observe")])

        text = stack.format_for_perception()
        assert "step 1/2" in text
        assert "look" in text


class TestBuildPlanPrompt:
    """Tests for build_plan_prompt."""

    def test_prompt_includes_drive_name(self) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        prompt = build_plan_prompt(
            goal=goal,
            drive_states={"curiosity": {"value": 0.8}},
            available_actions=["look", "observe"],
            recent_results=[],
        )
        assert "curiosity" in prompt
        assert "look" in prompt
        assert "observe" in prompt

    def test_prompt_includes_recent_results(self) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8)
        results = [ActionResult(action_type="look", success=True)]
        prompt = build_plan_prompt(
            goal=goal,
            drive_states={"curiosity": {"value": 0.8}},
            available_actions=["look"],
            recent_results=results,
        )
        assert "look: success" in prompt

    def test_prompt_notes_replan_attempt(self) -> None:
        goal = Goal(drive_name="curiosity", priority=0.8, attempts=1)
        prompt = build_plan_prompt(
            goal=goal,
            drive_states={"curiosity": {"value": 0.8}},
            available_actions=["look"],
            recent_results=[],
        )
        assert "re-plan attempt" in prompt


class TestDriveActionVocabulary:
    """Tests for the drive action vocabulary configuration."""

    def test_all_common_drives_have_vocabulary(self) -> None:
        expected_drives = [
            "energy",
            "integrity",
            "arousal",
            "competence",
            "certainty",
            "curiosity",
            "affiliation",
            "recognition",
            "individuation",
        ]
        for drive in expected_drives:
            assert drive in DRIVE_ACTION_VOCABULARY
            assert len(DRIVE_ACTION_VOCABULARY[drive]) > 0
