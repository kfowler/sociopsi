"""Tests for physical state monitoring."""

import pytest
from sociopsi.utils.physical_state import PhysicalState


def test_get_battery_percent():
    """Test getting battery percentage."""
    state = PhysicalState()
    battery = state.get_battery_percent()

    # Battery should be between 0 and 100 (or None if no battery)
    if battery is not None:
        assert 0 <= battery <= 100


def test_get_cpu_percent():
    """Test getting CPU usage percentage."""
    state = PhysicalState()
    cpu = state.get_cpu_percent()

    assert 0 <= cpu <= 100


def test_is_plugged_in():
    """Test checking if power is plugged in."""
    state = PhysicalState()
    plugged = state.is_plugged_in()

    assert isinstance(plugged, bool) or plugged is None


def test_get_state_dict():
    """Test getting full state as dictionary."""
    state = PhysicalState()
    state_dict = state.get_state()

    assert "battery_percent" in state_dict
    assert "cpu_percent" in state_dict
    assert "is_plugged_in" in state_dict
