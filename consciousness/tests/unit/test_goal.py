"""Tests for Goal class."""

import pytest
import time
from sociopsi.subsystems.goals.goal import Goal, GoalStatus


def test_goal_initialization():
    """Test Goal initialization with defaults."""
    goal = Goal(
        description="Test goal",
        related_drive="affiliation",
        priority=0.8,
    )

    assert goal.description == "Test goal"
    assert goal.related_drive == "affiliation"
    assert goal.priority == 0.8
    assert goal.status == GoalStatus.PENDING
    assert goal.id is not None  # Should have UUID
    assert goal.created_at > 0
    assert goal.started_at is None
    assert goal.completed_at is None


def test_goal_activate():
    """Test activating a goal."""
    goal = Goal(description="Test goal")

    assert goal.status == GoalStatus.PENDING
    assert goal.started_at is None

    goal.activate()

    assert goal.status == GoalStatus.ACTIVE
    assert goal.started_at is not None
    assert goal.is_active()


def test_goal_complete_success():
    """Test completing a goal successfully."""
    goal = Goal(description="Test goal")
    goal.activate()

    goal.complete(success=True)

    assert goal.status == GoalStatus.COMPLETED
    assert goal.completed_at is not None
    assert goal.is_complete()


def test_goal_complete_failure():
    """Test goal failure."""
    goal = Goal(description="Test goal")
    goal.activate()

    goal.complete(success=False)

    assert goal.status == GoalStatus.FAILED
    assert goal.completed_at is not None
    assert goal.is_complete()


def test_goal_abandon():
    """Test abandoning a goal."""
    goal = Goal(description="Test goal")
    goal.activate()

    goal.abandon()

    assert goal.status == GoalStatus.ABANDONED
    assert goal.completed_at is not None
    assert goal.is_complete()


def test_goal_is_active():
    """Test is_active check."""
    goal = Goal(description="Test goal")

    assert not goal.is_active()

    goal.activate()
    assert goal.is_active()

    goal.complete(success=True)
    assert not goal.is_active()


def test_goal_is_complete():
    """Test is_complete check."""
    goal = Goal(description="Test goal")

    assert not goal.is_complete()

    goal.activate()
    assert not goal.is_complete()

    goal.complete(success=True)
    assert goal.is_complete()


def test_goal_get_elapsed_time():
    """Test elapsed time calculation."""
    goal = Goal(description="Test goal")

    # Not started
    assert goal.get_elapsed_time() == 0.0

    # Started
    goal.activate()
    time.sleep(0.1)
    elapsed = goal.get_elapsed_time()
    assert elapsed >= 0.1
    assert elapsed < 1.0  # Reasonable bound

    # Completed
    goal.complete(success=True)
    final_elapsed = goal.get_elapsed_time()
    assert final_elapsed >= elapsed


def test_goal_check_timeout():
    """Test timeout checking."""
    goal = Goal(
        description="Test goal",
        success_criteria={"timeout": 0.1},  # 100ms timeout
    )

    assert not goal.check_timeout()  # Not started

    goal.activate()
    assert not goal.check_timeout()  # Just started

    time.sleep(0.15)  # Wait past timeout
    assert goal.check_timeout()


def test_goal_check_timeout_no_timeout_set():
    """Test timeout check when no timeout specified."""
    goal = Goal(
        description="Test goal",
        success_criteria={},
    )

    goal.activate()
    time.sleep(0.1)

    assert not goal.check_timeout()  # No timeout means never times out


def test_goal_to_dict():
    """Test converting goal to dictionary."""
    goal = Goal(
        description="Test goal",
        related_drive="affiliation",
        priority=0.7,
        proposing_archetype="shadow",
        success_criteria={"timeout": 60.0},
    )

    goal_dict = goal.to_dict()

    assert goal_dict["description"] == "Test goal"
    assert goal_dict["related_drive"] == "affiliation"
    assert goal_dict["priority"] == 0.7
    assert goal_dict["proposing_archetype"] == "shadow"
    assert goal_dict["status"] == "pending"
    assert "id" in goal_dict
    assert "created_at" in goal_dict
    assert "elapsed_time" in goal_dict
