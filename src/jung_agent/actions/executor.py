"""Main action executor that dispatches to specific handlers."""

from typing import Any

from jung_agent.actions import communication, environment, memory, perception, system
from jung_agent.config import AgentConfig
from jung_agent.types import Action, ActionResult


class ActionExecutor:
    """Executes actions requested by the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._heartbeat_override: int | None = None

        # Initialize memory
        self._memory = memory.MemoryStore(config.memory_file)
        self._journal = memory.Journal(config.journal_file)

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
            # External senses
            "look": perception.look,
            "look_for": perception.look_for,
            "watch": perception.watch,
            "listen": perception.listen,
            "listen_for": perception.listen_for,
            "transcribe": perception.transcribe,
            "sense_light": perception.sense_light,
            "sense_motion": perception.sense_motion,
            "sense_touch": perception.sense_touch,
            "sense_presence": perception.sense_presence,
            "sense_location": perception.sense_location,
            "sense_connections": perception.sense_connections,
            "sense_breath": perception.sense_breath,
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
            "disconnect_network": environment.disconnect_network,
            # Memory
            "journal_write": self._journal_write,
            "journal_read": self._journal_read,
            "store_memory": self._store_memory,
            "recall_memory": self._recall_memory,
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
        """Write to journal."""
        self._journal.write(entry, mood, somatic_snapshot)
        return {"written": True, "entry_preview": entry[:50] + "..." if len(entry) > 50 else entry}

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
