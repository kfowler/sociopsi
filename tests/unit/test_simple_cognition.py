"""Tests for simple rule-based cognition."""

import pytest
from sociopsi.subsystems.cognition.simple import SimpleCognition
from sociopsi.core.event_bus import EventBus


def test_simple_cognition_initialization():
    """Test simple cognition initialization."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    assert cognition.event_bus == bus


def test_generate_thought_high_drives():
    """Test thought generation when drives are satisfied."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.8, "below_threshold": False},
        "nurturing": {"value": 0.7, "below_threshold": False},
    }

    thought = cognition.generate_thought(drive_state)

    assert "content" in thought or "satisfied" in thought.lower()


def test_generate_thought_low_affiliation():
    """Test thought when affiliation drive is low."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.2, "below_threshold": True},
        "nurturing": {"value": 0.7, "below_threshold": False},
    }

    thought = cognition.generate_thought(drive_state)

    assert "lonely" in thought.lower() or "connection" in thought.lower()


def test_generate_thought_low_nurturing():
    """Test thought when nurturing drive is low."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.7, "below_threshold": False},
        "nurturing": {"value": 0.2, "below_threshold": True},
    }

    thought = cognition.generate_thought(drive_state)

    assert "contribute" in thought.lower() or "useful" in thought.lower()
