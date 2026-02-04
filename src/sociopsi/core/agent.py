"""Main agent loop integrating all subsystems."""

import asyncio
import time
from typing import Optional

from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.subsystems.perception.visual import VisualPerception
from sociopsi.subsystems.cognition.simple import SimpleCognition
from sociopsi.utils.physical_state import PhysicalState
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiAgent:
    """Main Socio-Psi agent integrating all subsystems."""

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize agent.

        Args:
            config: Configuration (uses default if None)
        """
        self.config = config or Config()
        self.event_bus = EventBus()

        # Initialize subsystems
        self.drive_system = DriveSystem(self.event_bus, self.config)
        self.visual_perception = VisualPerception(self.event_bus)
        self.cognition = SimpleCognition(self.event_bus)
        self.physical_state = PhysicalState()

        # TUI will be set externally
        self.tui: Optional[SocioPsiTUI] = None

        # Subscribe to events for TUI updates
        self._setup_event_handlers()

        # Loop control
        self.running = False
        self.last_update_time = time.time()

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for TUI updates."""
        self.event_bus.subscribe("drives.updated", self._on_drive_updated)
        self.event_bus.subscribe("cognition.thought", self._on_thought)
        self.event_bus.subscribe("perception.visual.face_detected", self._on_face_detected)

    def _on_drive_updated(self, data: dict) -> None:
        """Handle drive update event."""
        if self.tui is not None:
            drive_name = data["drive_name"]
            drive = self.drive_system.drives[drive_name]
            self.tui.update_drive(drive_name, drive.value, drive.base_threshold)

    def _on_thought(self, data: dict) -> None:
        """Handle thought event."""
        if self.tui is not None:
            self.tui.add_thought(data["thought"])

    def _on_face_detected(self, data: dict) -> None:
        """Handle face detection event."""
        if self.tui is not None:
            count = data["count"]
            self.tui.update_perception(f"{count} face(s) detected")

        # Satisfy affiliation drive
        self.drive_system.satisfy_drive("affiliation", amount=0.1)

    async def start(self) -> None:
        """Start the agent main loop."""
        self.running = True

        # Start camera
        if not self.visual_perception.start_camera():
            print("Warning: Could not start camera")

        # Main loop
        while self.running:
            await self.update()
            await asyncio.sleep(0.1)  # ~10 FPS for now

    def stop(self) -> None:
        """Stop the agent."""
        self.running = False
        self.visual_perception.stop_camera()

    async def update(self) -> None:
        """Update all subsystems for one tick."""
        # Calculate delta time
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Get physical state
        physical_state = self.physical_state.get_state()

        # Update drives (decay)
        self.drive_system.update(dt, physical_state)

        # Process perception
        frame = self.visual_perception.read_frame()
        if frame is not None:
            self.visual_perception.process_frame(frame)

        # Update cognition
        drive_state = self.drive_system.get_state()
        self.cognition.update(drive_state, physical_state)
