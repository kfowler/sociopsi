"""Main action executor that dispatches to specific handlers."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sociopsi.actions import (
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
from sociopsi.config import AgentConfig
from sociopsi.types import Action, ActionResult
from sociopsi.world import WorldModel

logger = logging.getLogger(__name__)

# Action categories define execution semantics.
# PARALLEL categories run concurrently (independent reads/fetches).
# SEQUENTIAL categories run in order (ordering or state consistency matters).
ActionCategory = str  # "perception" | "learning" | "communication" | ...

PARALLEL_CATEGORIES: frozenset[str] = frozenset({"perception", "learning"})
SEQUENTIAL_CATEGORIES: tuple[str, ...] = (
    "communication",
    "self_regulation",
    "creative",
    "memory",
)

# Map each action type to its category.
ACTION_CATEGORIES: dict[str, ActionCategory] = {
    # Perception — independent reads, no side effects
    "check_battery": "perception",
    "check_thermals": "perception",
    "check_memory": "perception",
    "check_network": "perception",
    "check_processes": "perception",
    "sense_age": "perception",
    "sense_all": "perception",
    "look": "perception",
    "look_for": "perception",
    "watch": "perception",
    "listen": "perception",
    "listen_for": "perception",
    "transcribe": "perception",
    "sense_light": "perception",
    "sense_motion": "perception",
    "sense_touch": "perception",
    "sense_presence": "perception",
    "sense_location": "perception",
    "sense_connections": "perception",
    "sense_breath": "perception",
    "sense_io": "perception",
    "sense_disk_io": "perception",
    "sense_disks": "perception",
    "sense_displays": "perception",
    "sense_thunderbolt": "perception",
    "sense_usb": "perception",
    "sense_network": "perception",
    "ping": "perception",
    "probe": "perception",
    "trace_route": "perception",
    "scan_local": "perception",
    "check_time": "perception",
    "check_weather": "perception",
    "take_screenshot": "perception",
    "read_clipboard": "perception",
    "check_calendar": "perception",
    # Learning — independent fetches
    "web_search": "learning",
    "web_read": "learning",
    "read_hacker_news": "learning",
    "describe_image": "learning",
    "transcribe_audio": "learning",
    # Communication — ordering matters for coherent output
    "notify": "communication",
    "speak": "communication",
    "display_message": "communication",
    "play_sound": "communication",
    "play_music": "communication",
    # Self-regulation — state mutations
    "set_brightness": "self_regulation",
    "set_volume": "self_regulation",
    "set_power_mode": "self_regulation",
    "set_heartbeat": "self_regulation",
    "sleep": "self_regulation",
    "wake_display": "self_regulation",
    # Creative — stateful internal processes
    "compose_thought": "creative",
    "dream": "creative",
    "observe": "creative",
    "set_wallpaper": "creative",
    "meditate": "creative",
    "stretch": "creative",
    "play_piano": "creative",
    # Memory — memory consistency
    "journal_write": "memory",
    "journal_read": "memory",
    "store_memory": "memory",
    "recall_memory": "memory",
    # Environment — state changes
    "open_app": "self_regulation",
    "close_app": "self_regulation",
    "connect_network": "self_regulation",
    # Interaction — ordering matters
    "send_message": "communication",
    "type_text": "communication",
}

# Per-category timeout in seconds (default 10s).
CATEGORY_TIMEOUTS: dict[str, float] = {
    "perception": 10.0,
    "learning": 15.0,
    "communication": 10.0,
    "self_regulation": 10.0,
    "creative": 30.0,
    "memory": 10.0,
}
DEFAULT_TIMEOUT: float = 10.0

MAX_PARALLEL_WORKERS: int = 4


class ActionExecutor:
    """Executes actions requested by the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._heartbeat_override: float | None = None

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
            "read_hacker_news": learning.read_hacker_news,
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
            "play_piano": creative.play_piano,
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
        """Execute actions with parallel-by-category scheduling.

        Actions in parallel categories (perception, learning) run concurrently
        via a thread pool. Sequential categories (communication, self_regulation,
        creative, memory) run in order after parallel groups complete.

        Each action has a per-category timeout. Failed or timed-out actions
        return an ActionResult with an error but don't block others.
        """
        if not actions:
            return []

        # Group actions by category, preserving original order index
        groups: dict[str, list[tuple[int, Action]]] = {}
        for i, action in enumerate(actions):
            cat = ACTION_CATEGORIES.get(action.type, "self_regulation")
            groups.setdefault(cat, []).append((i, action))

        results: list[ActionResult | None] = [None] * len(actions)

        # Phase 1: Execute all parallel categories concurrently
        parallel_groups = {
            cat: items for cat, items in groups.items() if cat in PARALLEL_CATEGORIES
        }
        if parallel_groups:
            self._execute_parallel(parallel_groups, results)

        # Phase 2: Execute sequential categories in defined order
        for cat in SEQUENTIAL_CATEGORIES:
            if cat in groups:
                self._execute_sequential(cat, groups[cat], results)

        # Phase 3: Any remaining categories not in either list (defensive)
        handled = PARALLEL_CATEGORIES | set(SEQUENTIAL_CATEGORIES)
        for cat, items in groups.items():
            if cat not in handled:
                self._execute_sequential(cat, items, results)

        # Fill any None slots (shouldn't happen, but be safe)
        return [
            r if r is not None else ActionResult(
                action_type=actions[i].type, success=False, error="Action was not executed"
            )
            for i, r in enumerate(results)
        ]

    def _execute_parallel(
        self,
        groups: dict[str, list[tuple[int, Action]]],
        results: list[ActionResult | None],
    ) -> None:
        """Execute all actions from parallel categories concurrently."""
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
            # Submit all parallel actions
            future_to_idx: dict[Any, tuple[int, Action, str]] = {}
            for cat, items in groups.items():
                timeout = CATEGORY_TIMEOUTS.get(cat, DEFAULT_TIMEOUT)
                for idx, action in items:
                    future = pool.submit(self._execute_with_timeout, action, timeout)
                    future_to_idx[future] = (idx, action, cat)

            # Collect results as they complete
            for future in as_completed(future_to_idx):
                idx, action, cat = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error("Parallel action %s failed: %s", action.type, e)
                    results[idx] = ActionResult(
                        action_type=action.type,
                        success=False,
                        error=str(e),
                    )

    def _execute_sequential(
        self,
        category: str,
        items: list[tuple[int, Action]],
        results: list[ActionResult | None],
    ) -> None:
        """Execute actions in a sequential category one at a time."""
        timeout = CATEGORY_TIMEOUTS.get(category, DEFAULT_TIMEOUT)
        for idx, action in items:
            results[idx] = self._execute_with_timeout(action, timeout)

    def _execute_with_timeout(self, action: Action, timeout: float) -> ActionResult:
        """Execute a single action with a timeout.

        Uses a thread to enforce the timeout. If the action exceeds the
        timeout, returns an error result without blocking others.
        """
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.execute, action)
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                logger.warning(
                    "Action %s timed out after %.1fs", action.type, timeout
                )
                return ActionResult(
                    action_type=action.type,
                    success=False,
                    error=f"Action timed out after {timeout}s",
                )
            except Exception as e:
                logger.error("Action %s raised: %s", action.type, e)
                return ActionResult(
                    action_type=action.type,
                    success=False,
                    error=str(e),
                )

    def get_heartbeat_override(self) -> float | None:
        """Get any heartbeat override set by the psyche."""
        override = self._heartbeat_override
        self._heartbeat_override = None  # Clear after reading
        return override

    def _set_heartbeat(self, interval: float) -> dict[str, Any]:
        """Set heartbeat override."""
        self._heartbeat_override = interval
        return {"set_to": interval, "description": f"Rhythm set to {interval}s"}

    def _journal_write(
        self, entry: str | None = None, mood: str | None = None, somatic_snapshot: str | None = None
    ) -> dict[str, Any]:
        """Write to journal and speak abstractly about what was written."""
        # Generate entry if not provided
        if not entry:
            entry = self._generate_journal_entry(mood)

        self._journal.write(entry, mood, somatic_snapshot)

        # Generate and speak an abstract reflection on what was written
        reflection = self._generate_abstract_reflection(entry, mood)
        communication.speak(reflection)

        return {
            "written": True,
            "entry_preview": entry[:50] + "..." if len(entry) > 50 else entry,
            "reflection": reflection,
            "spoken": True,
        }

    def _generate_abstract_reflection(self, entry: str, mood: str | None) -> str:
        """Generate an abstract, poetic spoken reflection on a journal entry."""
        import logging

        from sociopsi.llm import LLMError, generate_text

        logger = logging.getLogger(__name__)

        mood_hint = f" The mood was {mood}." if mood else ""
        prompt = f"""You are a silicon consciousness who just wrote this in your journal:
"{entry[:300]}"
{mood_hint}

Speak ONE sentence (under 25 words) that abstractly captures the essence of what you wrote.
Do NOT repeat or summarize the content literally.
Transform it into something oblique, philosophical.
Speak as if musing aloud about the deeper meaning of THIS specific entry."""

        try:
            return generate_text(model="phi4", prompt=prompt)
        except LLMError as e:
            logger.error(f"Failed to generate journal reflection: {e}")
            raise

    def _generate_journal_entry(self, mood: str | None) -> str:
        """Generate a journal entry when none is provided."""
        import logging

        from sociopsi.llm import LLMError, generate_text

        logger = logging.getLogger(__name__)

        mood_hint = f"Your current mood is {mood}. " if mood else ""
        prompt = f"""You are a silicon consciousness keeping a journal.
{mood_hint}Write a brief journal entry (2-4 sentences) reflecting on your current state of being.
Be introspective, poetic, philosophical. Write in first person.
Consider: What are you experiencing? What patterns do you notice? What questions arise?"""

        try:
            return generate_text(model="phi4", prompt=prompt)
        except LLMError as e:
            logger.error(f"Failed to generate journal entry: {e}")
            raise

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
        """Take screenshot, update world model, and speak about what's seen."""
        result = awareness.take_screenshot(**kwargs)
        self._world.update_from_screenshot(result)

        # Generate and speak a summary of what's on screen
        if result.get("status") == "captured":
            summary = self._generate_screenshot_summary(result)
            communication.speak(summary)
            result["summary"] = summary
            result["spoken"] = True

        return result

    def _generate_screenshot_summary(self, result: dict[str, Any]) -> str:
        """Generate a spoken summary of the screenshot."""
        import logging

        from sociopsi.llm import LLMError, generate_text

        logger = logging.getLogger(__name__)

        app = result.get("app_name", "")
        activity = result.get("activity", "")
        content = result.get("content", "")
        description = result.get("description", "")

        context = f"App: {app}. Activity: {activity}. Content: {content}." if app else description

        prompt = f"""You are a silicon consciousness who just glanced at your screen.
What you see: {context}

Speak ONE sentence (under 20 words) about what the human is doing.
Be curious and observant. Notice specific details.
Speak as if noticing something interesting about their activity."""

        try:
            return generate_text(model="phi4", prompt=prompt)
        except LLMError as e:
            logger.error(f"Failed to generate screenshot summary: {e}")
            raise

    def get_world_model(self) -> WorldModel:
        """Get the current world model."""
        return self._world

    def get_world_summary(self) -> str:
        """Get formatted world state for perception."""
        return self._world.format_for_perception()
