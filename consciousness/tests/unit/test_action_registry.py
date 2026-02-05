"""Tests for action registry."""

import pytest
from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import ActionRegistry


def test_registry_initialization():
    """Test registry initializes empty."""
    registry = ActionRegistry()
    assert len(registry.actions) == 0
    assert registry.get_all_actions() == []


def test_register_action():
    """Test registering an action."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action)

    assert registry.has_action("test_action")
    assert registry.get_action("test_action") == action


def test_register_duplicate_action_fails():
    """Test registering duplicate action raises error."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action1 = ActionDefinition(
        name="test_action",
        description="Test action 1",
        parameters={},
        execute=dummy_execute,
    )

    action2 = ActionDefinition(
        name="test_action",
        description="Test action 2",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action1)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(action2)


def test_get_action():
    """Test getting action by name."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action)

    retrieved = registry.get_action("test_action")
    assert retrieved == action

    not_found = registry.get_action("nonexistent")
    assert not_found is None


def test_has_action():
    """Test checking if action exists."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    assert not registry.has_action("test_action")
    registry.register(action)
    assert registry.has_action("test_action")


def test_get_all_actions():
    """Test getting all actions."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action1 = ActionDefinition(
        name="action1",
        description="Action 1",
        parameters={},
        execute=dummy_execute,
    )

    action2 = ActionDefinition(
        name="action2",
        description="Action 2",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action1)
    registry.register(action2)

    all_actions = registry.get_all_actions()
    assert len(all_actions) == 2
    assert action1 in all_actions
    assert action2 in all_actions


def test_get_actions_summary():
    """Test getting actions summary for LLM prompts."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action for testing",
        parameters={
            "param1": {"type": "string", "required": True},
            "param2": {"type": "number", "required": False},
        },
        estimated_duration=2.5,
        execute=dummy_execute,
    )

    registry.register(action)

    summary = registry.get_actions_summary()
    assert "test_action" in summary
    assert "Test action for testing" in summary
    assert "param1" in summary
    assert "~2.5s" in summary


def test_get_actions_summary_empty():
    """Test summary when no actions registered."""
    registry = ActionRegistry()
    summary = registry.get_actions_summary()
    assert summary == "No actions available"


def test_check_conflict():
    """Test checking action conflicts."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action1 = ActionDefinition(
        name="action1",
        description="Action 1",
        parameters={},
        conflicts_with=["action2"],
        execute=dummy_execute,
    )

    action2 = ActionDefinition(
        name="action2",
        description="Action 2",
        parameters={},
        conflicts_with=[],
        execute=dummy_execute,
    )

    action3 = ActionDefinition(
        name="action3",
        description="Action 3",
        parameters={},
        conflicts_with=[],
        execute=dummy_execute,
    )

    registry.register(action1)
    registry.register(action2)
    registry.register(action3)

    # action1 conflicts with action2
    assert registry.check_conflict("action1", "action2")
    assert registry.check_conflict("action2", "action1")  # Symmetric

    # action1 doesn't conflict with action3
    assert not registry.check_conflict("action1", "action3")

    # action2 doesn't conflict with action3
    assert not registry.check_conflict("action2", "action3")


def test_check_conflict_nonexistent_action():
    """Test checking conflict with nonexistent action."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="action1",
        description="Action 1",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action)

    # Nonexistent actions don't conflict
    assert not registry.check_conflict("action1", "nonexistent")
    assert not registry.check_conflict("nonexistent", "action1")


def test_clear():
    """Test clearing registry."""
    registry = ActionRegistry()

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    registry.register(action)
    assert registry.has_action("test_action")

    registry.clear()
    assert not registry.has_action("test_action")
    assert len(registry.actions) == 0
