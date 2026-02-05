"""Command input widget for TUI."""

import time

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input

from sociopsi.core.event_bus import EventBus


class CommandInput(Container):
    """Command input widget with history."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize command input.

        Args:
            event_bus: Event bus for publishing commands
        """
        super().__init__()
        self.event_bus = event_bus
        self.history: list[str] = []
        self.history_index = 0

    def compose(self) -> ComposeResult:
        """Compose widget layout."""
        yield Input(placeholder="Type a command...", id="command-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission.

        Args:
            event: Input submitted event
        """
        text = event.value.strip()
        if text:
            self.on_submit(text)
            event.input.value = ""  # Clear input

    def on_submit(self, text: str) -> None:
        """Publish command event.

        Args:
            text: Command text
        """
        self.event_bus.publish(
            "command.received", {"text": text, "source": "text", "timestamp": time.time()}
        )
        self.history.append(text)
        self.history_index = len(self.history)
