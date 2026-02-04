"""Terminal UI using Textual."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Container, Vertical
from textual import events
from rich.text import Text


class DriveDisplay(Static):
    """Display drive levels as progress bars."""

    def __init__(self, drive_name: str, **kwargs) -> None:
        """Initialize drive display.

        Args:
            drive_name: Name of the drive to display
        """
        super().__init__(**kwargs)
        self.drive_name = drive_name
        self.drive_value = 1.0
        self.threshold = 0.5

    def update_drive(self, value: float, threshold: float) -> None:
        """Update drive value and refresh display."""
        self.drive_value = value
        self.threshold = threshold
        self.refresh()

    def render(self) -> Text:
        """Render drive as progress bar."""
        # Create progress bar
        bar_width = 20
        filled = int(self.drive_value * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Color based on value
        if self.drive_value >= 0.7:
            color = "green"
        elif self.drive_value >= 0.4:
            color = "yellow"
        else:
            color = "red"

        # Add warning if below threshold
        warning = " ⚠️" if self.drive_value < self.threshold else ""

        text = Text()
        text.append(f"{self.drive_name.capitalize():12} ", style="bold")
        text.append(bar, style=color)
        text.append(f" {self.drive_value:.2f}{warning}")

        return text


class MonologueDisplay(Static):
    """Display scrolling internal monologue."""

    def __init__(self, **kwargs) -> None:
        """Initialize monologue display."""
        super().__init__(**kwargs)
        self.thoughts: list[str] = []
        self.max_thoughts = 10

    def add_thought(self, thought: str) -> None:
        """Add a new thought to the monologue."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.thoughts.append(f"[{timestamp}] {thought}")

        # Keep only recent thoughts
        if len(self.thoughts) > self.max_thoughts:
            self.thoughts = self.thoughts[-self.max_thoughts:]

        self.refresh()

    def render(self) -> str:
        """Render monologue."""
        if not self.thoughts:
            return "Awaiting thoughts..."
        return "\n".join(self.thoughts)


class SocioPsiTUI(App):
    """Socio-Psi Terminal UI."""

    CSS = """
    Screen {
        background: $surface;
    }

    #drives {
        height: auto;
        border: solid $primary;
        padding: 1;
    }

    #perception {
        height: auto;
        border: solid $primary;
        padding: 1;
    }

    #monologue {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    .section-title {
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause"),
    ]

    def __init__(self, **kwargs) -> None:
        """Initialize TUI."""
        super().__init__(**kwargs)
        self.drive_displays = {}
        self.monologue_display = None
        self.perception_display = None

    def compose(self) -> ComposeResult:
        """Compose UI layout."""
        yield Header()

        with Vertical():
            # Drives section
            with Container(id="drives"):
                yield Label("DRIVES", classes="section-title")
                self.drive_displays["affiliation"] = DriveDisplay("affiliation")
                self.drive_displays["nurturing"] = DriveDisplay("nurturing")
                yield self.drive_displays["affiliation"]
                yield self.drive_displays["nurturing"]

            # Perception section
            with Container(id="perception"):
                yield Label("PERCEPTION", classes="section-title")
                self.perception_display = Static("Visual: Initializing...")
                yield self.perception_display

            # Monologue section
            with Container(id="monologue"):
                yield Label("INTERNAL MONOLOGUE", classes="section-title")
                self.monologue_display = MonologueDisplay()
                yield self.monologue_display

        yield Footer()

    def update_drive(self, drive_name: str, value: float, threshold: float) -> None:
        """Update drive display."""
        if drive_name in self.drive_displays:
            self.drive_displays[drive_name].update_drive(value, threshold)

    def update_perception(self, text: str) -> None:
        """Update perception display."""
        if self.perception_display is not None:
            self.perception_display.update(f"Visual: {text}")

    def add_thought(self, thought: str) -> None:
        """Add thought to monologue."""
        if self.monologue_display is not None:
            self.monologue_display.add_thought(thought)

    def action_pause(self) -> None:
        """Pause/resume perception."""
        self.add_thought("[System] Pause not yet implemented")

    async def on_mount(self) -> None:
        """Handle mount event."""
        self.title = "Socio-Psi Mind"
        self.sub_title = "v0.1.0"
