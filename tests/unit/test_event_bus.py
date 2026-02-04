"""Tests for event bus."""

import pytest
from sociopsi.core.event_bus import EventBus


def test_subscribe_and_publish():
    """Test basic publish/subscribe."""
    bus = EventBus()
    events_received = []

    def handler(data: dict) -> None:
        events_received.append(data)

    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"value": 42})

    assert len(events_received) == 1
    assert events_received[0]["value"] == 42


def test_multiple_subscribers():
    """Test multiple handlers for same event."""
    bus = EventBus()
    received_a = []
    received_b = []

    bus.subscribe("test.event", lambda data: received_a.append(data))
    bus.subscribe("test.event", lambda data: received_b.append(data))
    bus.publish("test.event", {"value": 1})

    assert len(received_a) == 1
    assert len(received_b) == 1


def test_unsubscribe():
    """Test unsubscribing from events."""
    bus = EventBus()
    received = []

    def handler(data: dict) -> None:
        received.append(data)

    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"value": 1})
    bus.unsubscribe("test.event", handler)
    bus.publish("test.event", {"value": 2})

    assert len(received) == 1  # Only first event


def test_event_not_subscribed():
    """Test publishing to event with no subscribers."""
    bus = EventBus()
    # Should not raise
    bus.publish("no.subscribers", {"value": 1})
