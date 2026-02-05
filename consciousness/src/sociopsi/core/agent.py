"""Main agent loop integrating all subsystems."""

import asyncio
import time
from collections.abc import Mapping
from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.subsystems.perception.visual import VisualPerception
from sociopsi.subsystems.perception.audio import AudioPerception
from sociopsi.subsystems.archetypal_dialogue import ArchetypalDialogue
from sociopsi.subsystems.semantic_memory import SemanticMemory
from sociopsi.subsystems.metacognition import MetaCognition
from sociopsi.subsystems.goals.manager import GoalManager
from sociopsi.subsystems.planning.planner import ActionPlanner
from sociopsi.subsystems.execution.executor import ActionExecutor
from sociopsi.subsystems.commands import CommandProcessor, QueryHandler, SpeechInput
from sociopsi.subsystems.archetypes.modulator import ArchetypalModulator
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.actions.speak import SpeechAction, register_speak_action
from sociopsi.actions.registry import get_registry
from sociopsi.actions import update_display, focus_perception, adjust_volume, emit_sound, wait
from sociopsi.utils.physical_state import PhysicalState
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiAgent:
    """Main Socio-Psi agent integrating all subsystems."""

    def __init__(self, config: Config | None = None) -> None:
        """Initialize agent.

        Args:
            config: Configuration (uses default if None)
        """
        self.config = config or Config()
        self.event_bus = EventBus()

        # Initialize LLM client
        self.llm_client = OllamaClient(
            base_url=self.config.get("llm.base_url", "http://localhost:11434"),
            model=self.config.get("llm.model", "llama2"),
        )

        # Initialize subsystems
        self.drive_system = DriveSystem(self.event_bus, self.config)
        self.visual_perception = VisualPerception(self.event_bus)

        # Use semantic memory instead of basic memory
        self.memory_system = SemanticMemory(max_memories=100, forget_threshold=0.1)

        self.dialogue = ArchetypalDialogue(self.event_bus, self.llm_client, self.memory_system)
        self.physical_state = PhysicalState()

        # Add meta-cognition
        self.metacognition = MetaCognition(self.event_bus, self.llm_client, max_thoughts=5)

        # Initialize actions
        self.speech_action = SpeechAction(self.event_bus, enabled=True)

        # Register all actions in the registry
        self._register_actions()

        # Initialize Phase 4 systems (goal-directed behavior)
        self.goal_manager = GoalManager(self.event_bus, self.llm_client, self.drive_system)
        self.action_planner = ActionPlanner(self.event_bus, self.llm_client, get_registry())
        self.action_executor = ActionExecutor(
            self.event_bus, get_registry(), self.goal_manager, self.action_planner
        )

        # Connect archetypes to goal/planning systems
        self.goal_manager.set_archetypes(self.dialogue.archetypes, self.dialogue.ego)
        self.action_planner.set_archetypes(self.dialogue.archetypes, self.dialogue.ego)

        # Phase 5: Command processing
        self.command_processor = CommandProcessor(
            self.event_bus,
            list(self.dialogue.archetypes.values()),
            self.dialogue.ego,
            self.drive_system,
        )

        self.query_handler = QueryHandler(self.event_bus, self)

        # Phase 5: Speech input
        self.speech_input = SpeechInput(self.event_bus, self.config)

        # Phase 5: Audio perception
        self.audio_perception = AudioPerception(self.event_bus, self.config)

        # Phase 5: Archetypal modulation
        self.archetypal_modulator = ArchetypalModulator(self.event_bus, self.dialogue.archetypes)

        # TUI will be set externally
        self.tui: SocioPsiTUI | None = None

        # Goal generation control
        self.last_goal_check_time = time.time()
        self.goal_check_interval = 15.0  # Check for low drives every 15s

        # Subscribe to events for TUI updates
        self._setup_event_handlers()

        # Loop control
        self.running = False
        self.last_update_time = time.time()
        self.last_thought_time = time.time()
        self.thought_interval = 10.0  # Generate thought every 10 seconds
        self.last_reflection_time = time.time()
        self.reflection_interval = 30.0  # Reflect every 30 seconds

        # Physical state update throttling
        self.last_physical_update_time = time.time()
        self.physical_update_interval = 1.0  # Update TUI once per second

        # Background task tracking
        self.dialogue_task: asyncio.Task[None] | None = None
        self.reflection_task: asyncio.Task[None] | None = None

    def _register_actions(self) -> None:
        """Register all available actions."""
        register_speak_action(self.speech_action)
        update_display.register_update_display_action(self.event_bus)
        focus_perception.register_focus_perception_action(self.event_bus)
        adjust_volume.register_adjust_volume_action(self.event_bus, self.speech_action)
        emit_sound.register_emit_sound_action(self.event_bus)
        wait.register_wait_action(self.event_bus)

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for TUI updates."""
        self.event_bus.subscribe("drives.updated", self._on_drive_updated)
        self.event_bus.subscribe("dialogue.complete", self._on_dialogue_complete)
        self.event_bus.subscribe("dialogue.archetype_voice", self._on_archetype_voice)
        self.event_bus.subscribe("perception.visual.face_detected", self._on_face_detected)
        self.event_bus.subscribe("perception.audio.ambient", self._on_audio_ambient)
        self.event_bus.subscribe("metacognition.reflection", self._on_metacognition)

    def _on_drive_updated(self, data: dict[str, Any]) -> None:
        """Handle drive update event."""
        if self.tui is not None:
            # Log event to debug display
            if self.tui.debug_display is not None:
                self.tui.debug_display.log_event("drive", data.get("drive_name", "?"))

            drive_name = data["drive_name"]
            drive = self.drive_system.drives[drive_name]
            self.tui.update_drive(drive_name, drive.value, drive.base_threshold)

    def _on_dialogue_complete(self, data: dict[str, Any]) -> None:
        """Handle dialogue completion event."""
        if self.tui is not None:
            # Log event to debug display
            if self.tui.debug_display is not None:
                self.tui.debug_display.log_event("dialogue.complete")

            mediated_thought = data["mediated_thought"]
            harmony = data["harmony"]
            self.tui.add_thought(f"[Ego] {mediated_thought} (harmony: {harmony:.2f})")

            # Update individuation drive based on harmony
            self.drive_system.update_individuation(harmony)

        # Phase 5: Update command processor harmony tracking
        if hasattr(self, "command_processor"):
            self.command_processor.last_harmony = data["harmony"]

    def _on_archetype_voice(self, data: dict[str, Any]) -> None:
        """Handle archetype voice event."""
        if self.tui is not None:
            archetype = data["archetype"]
            voice = data["voice"]

            # Log event to debug display
            if self.tui.debug_display is not None:
                self.tui.debug_display.log_event("voice", archetype)

            # Truncate long voices for display
            display_voice = voice[:200] + "..." if len(voice) > 200 else voice
            self.tui.add_thought(f"[{archetype.capitalize()}] {display_voice}")

    def _on_face_detected(self, data: dict[str, Any]) -> None:
        """Handle face detection event."""
        if self.tui is not None:
            count = data["count"]
            self.tui.update_visual(count)

        # Satisfy affiliation drive
        self.drive_system.satisfy_drive("affiliation", amount=0.1)

    def _on_audio_ambient(self, data: dict[str, Any]) -> None:
        """Handle ambient audio perception event."""
        if self.tui is not None:
            sound_type = data.get("type", "unknown")
            volume = data.get("volume", 0.0)
            self.tui.update_audio(sound_type, volume)

    def _on_metacognition(self, data: dict[str, Any]) -> None:
        """Handle meta-cognition reflection event."""
        if self.tui is not None:
            # Log event to debug display
            if self.tui.debug_display is not None:
                self.tui.debug_display.log_event("metacognition")

            reflection = data["reflection"]
            harmony_trend = data["harmony_trend"]
            self.tui.add_thought(f"[Meta] {reflection} (trend: {harmony_trend})")

    async def start(self) -> None:
        """Start the agent main loop."""
        self.running = True

        # Start camera
        if not self.visual_perception.start_camera():
            print("Warning: Could not start camera")

        # Phase 5: Start audio perception
        await self.audio_perception.start()

        # Main loop
        while self.running:
            await self.update()
            await asyncio.sleep(0.1)  # ~10 FPS for now

    async def stop(self) -> None:
        """Stop the agent."""
        self.running = False

        # Cancel background tasks
        if self.dialogue_task and not self.dialogue_task.done():
            self.dialogue_task.cancel()
        if self.reflection_task and not self.reflection_task.done():
            self.reflection_task.cancel()

        self.visual_perception.stop_camera()
        self.speech_action.cleanup()

        # Phase 5: Stop audio perception
        if hasattr(self, "audio_perception"):
            await self.audio_perception.stop()

    async def update(self) -> None:
        """Update all subsystems for one tick."""
        # Calculate delta time
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Get physical state
        physical_state = self.physical_state.get_state()

        # Update TUI with physical state (throttled to avoid flooding)
        if self.tui is not None:
            if current_time - self.last_physical_update_time >= self.physical_update_interval:
                self.tui.update_physical(
                    physical_state["battery_percent"],
                    physical_state["cpu_percent"],
                    physical_state["is_plugged_in"],
                )
                self.last_physical_update_time = current_time

        # Update drives (decay)
        self.drive_system.update(dt, physical_state)

        # Update memory system (decay)
        self.memory_system.update(dt)

        # Process perception
        frame = self.visual_perception.read_frame()
        if frame is not None:
            self.visual_perception.process_frame(frame)

        # Phase 5: Update audio perception
        await self.audio_perception.update(dt)

        # Generate dialogue periodically (non-blocking)
        drive_state = self.drive_system.get_state()
        time_since_thought = current_time - self.last_thought_time

        if time_since_thought >= self.thought_interval:
            # Only start new dialogue if previous one is done
            if self.dialogue_task is None or self.dialogue_task.done():
                context = self._build_context(physical_state)

                async def generate_dialogue_with_error_handling():
                    try:
                        await self.dialogue.generate_dialogue(drive_state, context=context)
                    except Exception as e:
                        print(f"ERROR in dialogue generation: {e}")
                        import traceback

                        traceback.print_exc()

                self.dialogue_task = asyncio.create_task(generate_dialogue_with_error_handling())
                self.last_thought_time = current_time

        # Reflect periodically (meta-cognition, non-blocking)
        time_since_reflection = current_time - self.last_reflection_time

        if time_since_reflection >= self.reflection_interval:
            # Only start new reflection if previous one is done
            if self.reflection_task is None or self.reflection_task.done():

                async def reflect_with_error_handling():
                    try:
                        await self.metacognition.reflect(drive_state)
                    except Exception as e:
                        print(f"ERROR in meta-cognition: {e}")
                        import traceback

                        traceback.print_exc()

                self.reflection_task = asyncio.create_task(reflect_with_error_handling())
                self.last_reflection_time = current_time

        # Phase 4: Goal-directed behavior
        # Check for low drives and generate goals
        time_since_goal_check = current_time - self.last_goal_check_time

        if time_since_goal_check >= self.goal_check_interval:
            low_drives = [
                drive_name for drive_name, state in drive_state.items() if state["below_threshold"]
            ]

            if low_drives:
                await self.goal_manager.generate_goals(low_drives)

            self.last_goal_check_time = current_time

        # Update goal manager (activate pending goals, check timeouts)
        await self.goal_manager.update(dt)

        # Execute active goal plans
        await self.action_executor.update(dt)

    def _build_context(self, physical_state: Mapping[str, Any]) -> str:
        """Build context string for dialogue generation.

        Args:
            physical_state: Current physical state

        Returns:
            Context string
        """
        battery = physical_state.get("battery_percent", 0)
        plugged_in = physical_state.get("plugged_in", False)
        cpu = physical_state.get("cpu_percent", 0)

        context_parts = []

        if battery < 20 and not plugged_in:
            context_parts.append("Battery is low")
        if cpu > 80:
            context_parts.append("High CPU usage")

        if not context_parts:
            context_parts.append("All systems normal")

        return ", ".join(context_parts)
