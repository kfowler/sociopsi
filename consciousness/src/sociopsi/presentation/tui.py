"""Terminal UI using Textual."""

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Label, Static

from sociopsi.presentation.widgets import CommandInput

if TYPE_CHECKING:
    from sociopsi.core.agent import SocioPsiAgent


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

    # Archetype styling: (symbol, color)
    ARCHETYPE_STYLES = {
        "persona": ("🎭", "bright_blue"),
        "shadow": ("🌑", "red"),
        "anima": ("🌙", "green"),
        "self": ("☀️", "yellow"),
        "ego": ("👁", "bright_white"),
        "meta": ("🔮", "cyan"),
        "system": ("⚙️", "dim white"),
        "response": ("💬", "grey"),
        "test": ("🧪", "bright_yellow"),
    }

    def __init__(self, **kwargs) -> None:
        """Initialize monologue display."""
        super().__init__(**kwargs)
        self.thoughts: list[tuple[str, str, str]] = []  # (timestamp, archetype, content)
        self.max_thoughts = 10

    def add_thought(self, thought: str) -> None:
        """Add a new thought to the monologue."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Parse archetype from thought format: [Archetype] content
        archetype = "unknown"
        content = thought
        if thought.startswith("[") and "]" in thought:
            bracket_end = thought.index("]")
            archetype = thought[1:bracket_end].lower()
            content = thought[bracket_end + 1 :].strip()

        self.thoughts.append((timestamp, archetype, content))

        # Keep only recent thoughts
        if len(self.thoughts) > self.max_thoughts:
            self.thoughts = self.thoughts[-self.max_thoughts :]

        self.refresh()

    def render(self) -> Text:
        """Render monologue with styled archetype labels."""
        if not self.thoughts:
            return Text("Awaiting thoughts...", style="dim italic")

        output = Text()
        for i, (timestamp, archetype, content) in enumerate(self.thoughts):
            if i > 0:
                output.append("\n")

            # Get style for this archetype
            symbol, color = self.ARCHETYPE_STYLES.get(archetype, ("•", "white"))

            # Timestamp
            output.append(f"{timestamp} ", style="dim")
            # Symbol and archetype name
            output.append(f"{symbol} ", style=color)
            output.append(f"{archetype.upper():8} ", style=f"bold {color}")
            # Content
            output.append(content, style="white")

        return output


class PerceptionDisplay(Static):
    """Display all perception channels."""

    def __init__(self, **kwargs) -> None:
        """Initialize perception display."""
        super().__init__(**kwargs)
        self.visual_faces = 0
        self.audio_type = "silence"
        self.audio_volume = 0.0
        self.battery_percent = None
        self.cpu_percent = 0.0
        self.is_plugged_in = None

    def update_visual(self, face_count: int) -> None:
        """Update visual perception."""
        self.visual_faces = face_count
        self.refresh()

    def update_audio(self, sound_type: str, volume: float) -> None:
        """Update audio perception."""
        self.audio_type = sound_type
        self.audio_volume = volume
        self.refresh()

    def update_physical(self, battery: float | None, cpu: float, plugged_in: bool | None) -> None:
        """Update physical state."""
        self.battery_percent = battery
        self.cpu_percent = cpu
        self.is_plugged_in = plugged_in
        self.refresh()

    def render(self) -> Text:
        """Render all perceptions."""
        output = Text()

        # Visual
        output.append("👁 Visual   ", style="bold cyan")
        if self.visual_faces > 0:
            output.append(f"{self.visual_faces} face(s)", style="green")
        else:
            output.append("no faces", style="dim")

        output.append("\n")

        # Audio
        output.append("🔊 Audio    ", style="bold cyan")
        volume_bar = "█" * int(self.audio_volume * 10) + "░" * (10 - int(self.audio_volume * 10))
        audio_colors = {
            "silence": "green",
            "activity": "yellow",  # Voice or music
            "noise": "blue",
            "loud_noise": "red",
        }
        audio_color = audio_colors.get(self.audio_type, "white")
        output.append(f"{self.audio_type:12} ", style=audio_color)
        output.append(f"[{volume_bar}]", style="dim")

        output.append("\n")

        # Physical
        output.append("⚡ Physical ", style="bold cyan")
        if self.battery_percent is not None:
            batt_color = "green" if self.battery_percent > 20 else "red"
            plug_icon = "🔌" if self.is_plugged_in else "🔋"
            output.append(f"{plug_icon} {self.battery_percent:.0f}%  ", style=batt_color)
        cpu_color = (
            "green" if self.cpu_percent < 50 else "yellow" if self.cpu_percent < 80 else "red"
        )
        output.append(f"CPU {self.cpu_percent:.0f}%", style=cpu_color)

        return output


class DebugDisplay(Static):
    """Debug widget showing event flow."""

    def __init__(self, **kwargs) -> None:
        """Initialize debug display."""
        super().__init__(**kwargs)
        self.thought_count = 0
        self.last_event = "none"
        self.last_error = ""

    def log_event(self, event_type: str, details: str = "") -> None:
        """Log an event."""
        self.last_event = f"{event_type}: {details[:40]}" if details else event_type
        self.refresh()

    def log_thought(self) -> None:
        """Log that a thought was received."""
        self.thought_count += 1
        self.refresh()

    def log_error(self, error: str) -> None:
        """Log an error."""
        self.last_error = error[:50]
        self.refresh()

    def render(self) -> str:
        """Render debug info."""
        lines = [
            f"Thoughts received: {self.thought_count}",
            f"Last event: {self.last_event}",
        ]
        if self.last_error:
            lines.append(f"Error: {self.last_error}")
        return " | ".join(lines)


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
        min-height: 8;
        max-height: 20;
        border: solid $primary;
        padding: 1;
    }

    #debug {
        height: 3;
        dock: bottom;
        border: solid yellow;
        padding: 0 1;
        color: yellow;
    }

    #command {
        height: auto;
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
        Binding("ctrl+t", "test_thought", "Test", priority=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize TUI."""
        super().__init__(**kwargs)
        self.agent: SocioPsiAgent | None = None
        self.drive_displays: dict[str, DriveDisplay] = {}
        self.monologue_display: MonologueDisplay | None = None
        self.perception_display: PerceptionDisplay | None = None
        self.debug_display: DebugDisplay | None = None

    def compose(self) -> ComposeResult:
        """Compose UI layout."""
        yield Header()

        with Vertical():
            # Drives section
            with Container(id="drives"):
                yield Label("DRIVES", classes="section-title")
                self.drive_displays["affiliation"] = DriveDisplay("affiliation")
                self.drive_displays["nurturing"] = DriveDisplay("nurturing")
                self.drive_displays["individuation"] = DriveDisplay("individuation")
                yield self.drive_displays["affiliation"]
                yield self.drive_displays["nurturing"]
                yield self.drive_displays["individuation"]

            # Perception section
            with Container(id="perception"):
                yield Label("PERCEPTION", classes="section-title")
                self.perception_display = PerceptionDisplay()
                yield self.perception_display

            # Monologue section
            with Container(id="monologue"):
                yield Label("INTERNAL MONOLOGUE", classes="section-title")
                self.monologue_display = MonologueDisplay()
                yield self.monologue_display

            # Command input section
            if self.agent is not None:
                with Container(id="command"):
                    yield Label("COMMAND", classes="section-title")
                    yield CommandInput(self.agent.event_bus)

            # Debug section
            with Container(id="debug"):
                self.debug_display = DebugDisplay()
                yield self.debug_display

        yield Footer()

    def update_drive(self, drive_name: str, value: float, threshold: float) -> None:
        """Update drive display (thread-safe)."""

        def _update():
            if drive_name in self.drive_displays:
                self.drive_displays[drive_name].update_drive(value, threshold)

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            # If called from same thread, just run directly
            _update()

    def update_visual(self, face_count: int) -> None:
        """Update visual perception display."""

        def _update():
            if self.perception_display is not None:
                self.perception_display.update_visual(face_count)
                self.perception_display.refresh()

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()

    def update_audio(self, sound_type: str, volume: float) -> None:
        """Update audio perception display."""

        def _update():
            if self.perception_display is not None:
                self.perception_display.update_audio(sound_type, volume)
                self.perception_display.refresh()

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()

    def update_physical(self, battery: float | None, cpu: float, plugged_in: bool | None) -> None:
        """Update physical state display."""

        def _update():
            if self.perception_display is not None:
                self.perception_display.update_physical(battery, cpu, plugged_in)
                self.perception_display.refresh()

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()

    def add_thought(self, thought: str) -> None:
        """Add thought to monologue."""

        def _do_update():
            # Log to debug display
            if self.debug_display is not None:
                self.debug_display.log_thought()

            if self.monologue_display is not None:
                self.monologue_display.add_thought(thought)
                # Force refresh
                self.monologue_display.refresh(layout=True)
            elif self.debug_display is not None:
                self.debug_display.log_error("monologue_display is None")

        # Schedule on event loop to ensure proper rendering
        self.call_later(_do_update)

    def action_pause(self) -> None:
        """Pause/resume perception."""
        self.add_thought("[System] Pause not yet implemented")

    def action_test_thought(self) -> None:
        """Add a test thought to verify display works."""
        if self.monologue_display is not None:
            self.monologue_display.add_thought("[Test] Manual test thought triggered by 't' key")
        if self.debug_display is not None:
            self.debug_display.log_event("test", "manual trigger")

    async def on_mount(self) -> None:
        """Handle mount event."""
        self.title = "Socio-Psi Mind"
        self.sub_title = "v0.1.0"

        # Phase 5: Command response subscriptions
        if self.agent is not None:
            self.agent.event_bus.subscribe("command.response", self.on_command_response)
            self.agent.event_bus.subscribe("speech.recording.started", self.on_recording_started)
            self.agent.event_bus.subscribe("speech.recording.stopped", self.on_recording_stopped)

    def on_command_response(self, data: dict[str, Any]) -> None:
        """Handle command response event (thread-safe).

        Args:
            data: Response data with 'text' and 'query'
        """
        response_text = data["text"]

        def _update():
            if self.monologue_display is not None:
                self.monologue_display.add_thought(f"[Response] {response_text}")

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()

    def on_recording_started(self, data: dict[str, Any]) -> None:
        """Visual indicator that recording is active (thread-safe).

        Args:
            data: Recording start event data
        """

        def _update():
            if self.monologue_display is not None:
                self.monologue_display.add_thought("[System] Recording started...")

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()

    def on_recording_stopped(self, data: dict[str, Any]) -> None:
        """Remove recording indicator and show transcription (thread-safe).

        Args:
            data: Recording stop event data with 'transcribed'
        """
        transcribed = data.get("transcribed", "")

        def _update():
            if self.monologue_display is not None:
                if transcribed:
                    self.monologue_display.add_thought(f"[Voice Command] {transcribed}")
                else:
                    self.monologue_display.add_thought(
                        "[System] Recording stopped (no speech detected)"
                    )

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            _update()
