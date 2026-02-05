import pytest
from sociopsi.presentation.widgets.command_input import CommandInput
from sociopsi.core.event_bus import EventBus


def test_command_input_initialization():
    """CommandInput widget initializes with event bus."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)
    assert widget.event_bus == event_bus
    assert widget.history == []


def test_command_input_submit_publishes_event():
    """Submitting command publishes command.received event."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)

    received_events = []
    event_bus.subscribe("command.received", lambda data: received_events.append(data))

    widget.on_submit("test command")

    assert len(received_events) == 1
    assert received_events[0]["text"] == "test command"
    assert received_events[0]["source"] == "text"
    assert "timestamp" in received_events[0]
    assert isinstance(received_events[0]["timestamp"], float)


def test_command_input_history():
    """Commands added to history."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)

    widget.on_submit("command 1")
    widget.on_submit("command 2")

    assert len(widget.history) == 2
    assert widget.history[0] == "command 1"
    assert widget.history[1] == "command 2"
