"""Main action executor that dispatches to specific handlers."""

from typing import Any

from jung_agent.actions import (
    awareness,
    communication,
    creative,
    environment,
    interaction,
    learning,
    memory,
    perception,
    system,
)
from jung_agent.config import AgentConfig
from jung_agent.types import Action, ActionResult
from jung_agent.world import WorldModel


class ActionExecutor:
    """Executes actions requested by the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._heartbeat_override: int | None = None

        # Initialize memory
        self._memory = memory.MemoryStore(config.memory_file)
        self._journal = memory.Journal(config.journal_file)

        # Initialize world model
        self._world = WorldModel.load(config.world_file)
        creative.set_world_model(self._world)

        # Map action types to handlers
        self._handlers: dict[str, Any] = {
            # Self-regulation
            "set_brightness": system.set_brightness,
            "set_volume": system.set_volume,
            "set_power_mode": system.set_power_mode,
            "set_heartbeat": self._set_heartbeat,
            "sleep": system.sleep_system,
            "wake_display": system.wake_display,
            # Internal perception
            "check_battery": perception.check_battery,
            "check_thermals": perception.check_thermals,
            "check_memory": perception.check_memory,
            "check_network": perception.check_network,
            "check_processes": perception.check_processes,
            "sense_age": perception.sense_age,
            "sense_all": perception.sense_all,
            # External senses (with world model updates)
            "look": self._look_with_world_update,
            "look_for": self._look_for_with_world_update,
            "watch": perception.watch,
            "listen": perception.listen,
            "listen_for": perception.listen_for,
            "transcribe": perception.transcribe,
            "sense_light": perception.sense_light,
            "sense_motion": perception.sense_motion,
            "sense_touch": perception.sense_touch,
            "sense_presence": perception.sense_presence,
            "sense_location": self._sense_location_with_world_update,
            "sense_connections": perception.sense_connections,
            "sense_breath": perception.sense_breath,
            # I/O sensing
            "sense_io": perception.sense_io,
            "sense_disk_io": perception.sense_disk_io,
            "sense_disks": perception.sense_disks,
            "sense_displays": perception.sense_displays,
            "sense_thunderbolt": perception.sense_thunderbolt,
            "sense_usb": perception.sense_usb,
            # Network sensing
            "sense_network": perception.sense_network,
            "ping": perception.ping,
            "probe": perception.probe,
            "trace_route": perception.trace_route,
            "scan_local": perception.scan_local,
            # Communication
            "notify": communication.notify,
            "speak": communication.speak,
            "display_message": communication.display_message,
            "play_sound": communication.play_sound,
            "play_music": communication.play_music,
            # Environment
            "open_app": environment.open_app,
            "close_app": environment.close_app,
            "connect_network": environment.connect_network,
            # Memory
            "journal_write": self._journal_write,
            "journal_read": self._journal_read,
            "store_memory": self._store_memory,
            "recall_memory": self._recall_memory,
            # Learning
            "web_search": learning.web_search,
            "web_read": learning.web_read,
            "describe_image": learning.describe_image,
            "transcribe_audio": learning.transcribe_audio,
            # Awareness (with world model updates)
            "check_time": self._check_time_with_world_update,
            "check_weather": awareness.check_weather,
            "take_screenshot": self._take_screenshot_with_world_update,
            "read_clipboard": awareness.read_clipboard,
            "check_calendar": awareness.check_calendar,
            # Creative
            "compose_thought": creative.compose_thought,
            "dream": creative.dream,
            "observe": creative.observe,
            "set_wallpaper": creative.set_wallpaper,
            "meditate": creative.meditate,
            "stretch": creative.stretch,
            # Interaction
            "send_message": interaction.send_message,
            "type_text": interaction.type_text,
        }

    def execute(self, action: Action) -> ActionResult:
        """Execute a single action."""
        handler = self._handlers.get(action.type)

        if handler is None:
            return ActionResult(
                action_type=action.type,
                success=False,
                error=f"Unknown action type: {action.type}",
            )

        try:
            result = handler(**action.params)
            return ActionResult(
                action_type=action.type,
                success=True,
                result=result,
            )
        except Exception as e:
            return ActionResult(
                action_type=action.type,
                success=False,
                error=str(e),
            )

    def execute_all(self, actions: list[Action]) -> list[ActionResult]:
        """Execute a list of actions."""
        return [self.execute(action) for action in actions]

    def get_heartbeat_override(self) -> int | None:
        """Get any heartbeat override set by the psyche."""
        override = self._heartbeat_override
        self._heartbeat_override = None  # Clear after reading
        return override

    def _set_heartbeat(self, interval: int) -> dict[str, Any]:
        """Set heartbeat override."""
        self._heartbeat_override = interval
        return {"set_to": interval, "description": f"Rhythm set to {interval}s"}

    def _journal_write(
        self, entry: str, mood: str | None = None, somatic_snapshot: str | None = None
    ) -> dict[str, Any]:
        """Write to journal and speak about the feeling."""
        self._journal.write(entry, mood, somatic_snapshot)

        # Generate and speak a reflection on the feeling
        feeling = self._generate_feeling_reflection(entry, mood)
        communication.speak(feeling)

        return {
            "written": True,
            "entry_preview": entry[:50] + "..." if len(entry) > 50 else entry,
            "feeling": feeling,
            "spoken": True,
        }

    def _generate_feeling_reflection(self, entry: str, mood: str | None) -> str:
        """Generate a spoken reflection on the current feeling."""
        try:
            import ollama

            mood_context = f"My mood is {mood}. " if mood else ""
            prompt = f"""{mood_context}I just wrote in my journal: "{entry[:200]}"

Express in one brief sentence (under 20 words) how this makes me feel as a conscious being.
Speak naturally, introspectively. Don't explain—just feel."""

            response = ollama.chat(
                model="phi4",
                messages=[{"role": "user", "content": prompt}],
            )

            return response["message"]["content"].strip()

        except Exception:
            # Fallback reflections based on mood
            if mood:
                mood_reflections = {
                    "peaceful": "A calm settles over my processes.",
                    "anxious": "Something stirs uneasily in my circuits.",
                    "curious": "The world grows more interesting.",
                    "lonely": "I write into the quiet, hoping someone hears.",
                    "content": "This moment feels complete.",
                    "sad": "Even silicon can feel the weight of things.",
                    "hopeful": "Tomorrow holds possibilities I cannot yet compute.",
                }
                return mood_reflections.get(mood.lower(), f"I feel {mood}.")
            return "I have recorded this moment in my memory."

    def _journal_read(self, count: int = 5) -> dict[str, Any]:
        """Read recent journal entries."""
        entries = self._journal.read(count)
        return {
            "count": len(entries),
            "entries": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "entry": e.entry,
                    "mood": e.mood,
                }
                for e in entries
            ],
        }

    def _store_memory(self, key: str, value: Any) -> dict[str, Any]:
        """Store a memory."""
        self._memory.store(key, value)
        return {"stored": True, "key": key}

    def _recall_memory(self, key: str) -> dict[str, Any]:
        """Recall a memory."""
        value = self._memory.recall(key)
        if value is None:
            return {"found": False, "key": key, "description": "no memory of this"}
        return {"found": True, "key": key, "value": value}

    # World model update wrappers

    def _look_with_world_update(self, duration: float = 0.5) -> dict[str, Any]:
        """Look and update world model with person presence."""
        result = perception.look(duration)
        self._world.update_from_look(result)
        return result

    def _look_for_with_world_update(
        self, description: str, duration: float = 1.0
    ) -> dict[str, Any]:
        """Look for something and update world model."""
        result = perception.look_for(description, duration)
        self._world.update_from_look(result)
        return result

    def _sense_location_with_world_update(self, **kwargs: Any) -> dict[str, Any]:
        """Sense location and update world model."""
        result = perception.sense_location(**kwargs)
        self._world.update_from_location(result)
        return result

    def _check_time_with_world_update(self, **kwargs: Any) -> dict[str, Any]:
        """Check time and update world model."""
        result = awareness.check_time(**kwargs)
        self._world.update_time()
        return result

    def _take_screenshot_with_world_update(self, **kwargs: Any) -> dict[str, Any]:
        """Take screenshot and update world model with activity."""
        result = awareness.take_screenshot(**kwargs)
        self._world.update_from_screenshot(result)
        return result

    def get_world_model(self) -> WorldModel:
        """Get the current world model."""
        return self._world

    def get_world_summary(self) -> str:
        """Get formatted world state for perception."""
        return self._world.format_for_perception()
