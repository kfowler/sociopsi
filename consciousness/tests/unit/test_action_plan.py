"""Tests for ActionPlan."""

from sociopsi.subsystems.planning.action_plan import ActionPlan, ActionStep


def test_action_step_creation():
    """Test creating an action step."""
    step = ActionStep(
        action_name="speak",
        parameters={"text": "Hello"},
        optional=False,
        timeout=5.0,
    )

    assert step.action_name == "speak"
    assert step.parameters == {"text": "Hello"}
    assert not step.optional
    assert step.timeout == 5.0


def test_action_plan_creation():
    """Test creating an action plan."""
    steps = [
        ActionStep("speak", {"text": "Hi"}),
        ActionStep("wait", {"duration": 2}),
    ]

    plan = ActionPlan(goal_id="goal123", steps=steps, created_at=123.0)

    assert plan.goal_id == "goal123"
    assert len(plan.steps) == 2
    assert plan.current_step == 0
    assert not plan.is_complete()


def test_action_plan_get_current_step():
    """Test getting current step."""
    steps = [
        ActionStep("speak", {"text": "Hi"}),
        ActionStep("wait", {"duration": 2}),
    ]

    plan = ActionPlan(goal_id="goal123", steps=steps)

    current = plan.get_current_step()
    assert current == steps[0]


def test_action_plan_advance():
    """Test advancing through steps."""
    steps = [
        ActionStep("speak", {"text": "Hi"}),
        ActionStep("wait", {"duration": 2}),
    ]

    plan = ActionPlan(goal_id="goal123", steps=steps)

    assert plan.current_step == 0
    plan.advance()
    assert plan.current_step == 1
    plan.advance()
    assert plan.current_step == 2
    assert plan.is_complete()


def test_action_plan_is_complete():
    """Test completion check."""
    steps = [ActionStep("speak", {"text": "Hi"})]

    plan = ActionPlan(goal_id="goal123", steps=steps)

    assert not plan.is_complete()
    plan.advance()
    assert plan.is_complete()


def test_action_plan_get_remaining_steps():
    """Test getting remaining steps."""
    steps = [
        ActionStep("speak", {"text": "1"}),
        ActionStep("speak", {"text": "2"}),
        ActionStep("speak", {"text": "3"}),
    ]

    plan = ActionPlan(goal_id="goal123", steps=steps)

    remaining = plan.get_remaining_steps()
    assert len(remaining) == 3

    plan.advance()
    remaining = plan.get_remaining_steps()
    assert len(remaining) == 2
    assert remaining[0].parameters["text"] == "2"
