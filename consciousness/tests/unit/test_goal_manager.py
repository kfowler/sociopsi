"""Tests for GoalManager."""

import pytest
from unittest.mock import Mock, AsyncMock
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.goals.manager import GoalManager
from sociopsi.subsystems.goals.goal import Goal, GoalStatus


def test_goal_manager_initialization():
    """Test GoalManager initialization."""
    bus = EventBus()
    llm = Mock()
    drives = Mock()

    manager = GoalManager(bus, llm, drives)

    assert manager.event_bus == bus
    assert manager.llm_client == llm
    assert manager.drive_system == drives
    assert len(manager.active_goals) == 0
    assert len(manager.pending_goals) == 0
    assert len(manager.completed_goals) == 0


def test_add_goal():
    """Test adding a goal to pending queue."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(description="Test goal")

    manager.add_goal(goal)

    assert len(manager.pending_goals) == 1
    assert manager.pending_goals[0] == goal


def test_add_goal_respects_max_pending():
    """Test max pending goals limit."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock(), max_pending_goals=2)

    goal1 = Goal(description="Goal 1")
    goal2 = Goal(description="Goal 2")
    goal3 = Goal(description="Goal 3")

    manager.add_goal(goal1)
    manager.add_goal(goal2)
    manager.add_goal(goal3)  # Should be rejected

    assert len(manager.pending_goals) == 2


def test_activate_goal():
    """Test activating a pending goal."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(description="Test goal")
    manager.add_goal(goal)

    assert goal.status == GoalStatus.PENDING
    assert len(manager.pending_goals) == 1
    assert len(manager.active_goals) == 0

    success = manager.activate_goal(goal.id)

    assert success
    assert goal.status == GoalStatus.ACTIVE
    assert len(manager.pending_goals) == 0
    assert len(manager.active_goals) == 1


def test_activate_goal_respects_max_active():
    """Test max active goals limit."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock(), max_active_goals=1)

    goal1 = Goal(description="Goal 1")
    goal2 = Goal(description="Goal 2")

    manager.add_goal(goal1)
    manager.add_goal(goal2)

    manager.activate_goal(goal1.id)
    success = manager.activate_goal(goal2.id)

    assert not success  # Second activation should fail
    assert len(manager.active_goals) == 1
    assert len(manager.pending_goals) == 1  # Goal 2 still pending


def test_complete_goal_success():
    """Test completing a goal successfully."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(description="Test goal")
    manager.add_goal(goal)
    manager.activate_goal(goal.id)

    manager.complete_goal(goal.id, success=True)

    assert goal.status == GoalStatus.COMPLETED
    assert len(manager.active_goals) == 0
    assert len(manager.completed_goals) == 1


def test_complete_goal_failure():
    """Test failing a goal."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(description="Test goal")
    manager.add_goal(goal)
    manager.activate_goal(goal.id)

    manager.complete_goal(goal.id, success=False)

    assert goal.status == GoalStatus.FAILED
    assert len(manager.active_goals) == 0
    assert len(manager.completed_goals) == 1


def test_abandon_goal():
    """Test abandoning a goal."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(description="Test goal")
    manager.add_goal(goal)
    manager.activate_goal(goal.id)

    manager.abandon_goal(goal.id)

    assert goal.status == GoalStatus.ABANDONED
    assert len(manager.active_goals) == 0
    assert len(manager.completed_goals) == 1


def test_completed_goals_respects_max_history():
    """Test completed goals history limit."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock(), max_history=2)

    goal1 = Goal(description="Goal 1")
    goal2 = Goal(description="Goal 2")
    goal3 = Goal(description="Goal 3")

    for goal in [goal1, goal2, goal3]:
        manager.add_goal(goal)
        manager.activate_goal(goal.id)
        manager.complete_goal(goal.id, success=True)

    assert len(manager.completed_goals) == 2
    # Should keep most recent (goal2 and goal3)
    assert goal1 not in manager.completed_goals


def test_check_success_criteria_baseline():
    """Test checking success criteria (baseline drive threshold)."""
    bus = EventBus()
    drives = Mock()
    drives.get_state.return_value = {
        "affiliation": {"value": 0.7, "below_threshold": False}
    }

    manager = GoalManager(bus, Mock(), drives)

    goal = Goal(
        description="Test goal",
        related_drive="affiliation",
        success_criteria={
            "baseline": {"drive": "affiliation", "threshold": 0.6}
        },
    )

    # Drive is 0.7, threshold is 0.6 -> success
    assert manager.check_success_criteria(goal)

    # Lower drive value
    drives.get_state.return_value = {
        "affiliation": {"value": 0.5, "below_threshold": True}
    }

    # Drive is 0.5, threshold is 0.6 -> not success
    assert not manager.check_success_criteria(goal)


def test_get_active_goals_sorted_by_priority():
    """Test active goals returned sorted by priority."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal1 = Goal(description="Goal 1", priority=0.3)
    goal2 = Goal(description="Goal 2", priority=0.8)
    goal3 = Goal(description="Goal 3", priority=0.5)

    for goal in [goal1, goal2, goal3]:
        manager.add_goal(goal)
        manager.activate_goal(goal.id)

    active = manager.get_active_goals()

    # Should be sorted by priority (highest first)
    assert active[0] == goal2  # 0.8
    assert active[1] == goal3  # 0.5
    assert active[2] == goal1  # 0.3


def test_get_state():
    """Test getting goal manager state."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal1 = Goal(description="Active goal")
    goal2 = Goal(description="Pending goal")

    manager.add_goal(goal1)
    manager.add_goal(goal2)
    manager.activate_goal(goal1.id)

    state = manager.get_state()

    assert state["active_count"] == 1
    assert state["pending_count"] == 1
    assert state["completed_count"] == 0
    assert len(state["active_goals"]) == 1
    assert len(state["pending_goals"]) == 1


@pytest.mark.asyncio
async def test_update_activates_pending_goals():
    """Test update activates pending goals when space available."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock(), max_active_goals=2)

    goal1 = Goal(description="Goal 1", priority=0.5)
    goal2 = Goal(description="Goal 2", priority=0.8)

    manager.add_goal(goal1)
    manager.add_goal(goal2)

    await manager.update(0.1)

    # Should activate highest priority goal
    assert len(manager.active_goals) == 1
    assert manager.active_goals[0] == goal2  # Higher priority


@pytest.mark.asyncio
async def test_update_checks_timeouts():
    """Test update abandons timed-out goals."""
    bus = EventBus()
    manager = GoalManager(bus, Mock(), Mock())

    goal = Goal(
        description="Test goal",
        success_criteria={"timeout": 0.01},  # Very short timeout
    )

    manager.add_goal(goal)
    manager.activate_goal(goal.id)

    import time
    time.sleep(0.02)  # Wait past timeout

    await manager.update(0.1)

    assert goal.status == GoalStatus.ABANDONED
    assert len(manager.active_goals) == 0
    assert len(manager.completed_goals) == 1
