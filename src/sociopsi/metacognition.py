"""Meta-cognition system for self-reflection.

Tracks thoughts, analyzes harmony trends, and generates reflections
on the agent's psychological state and processes.

Runs an independent background timer that generates reflections periodically.
The agent loop reads cached reflections via cached_reflection() rather than
calling reflect() synchronously.
"""

import logging
import threading
from collections import deque
from typing import Any

from sociopsi.event_bus import EventBus, get_event_bus
from sociopsi.llm import chat_with_retry

logger = logging.getLogger(__name__)


class MetaCognition:
    """Self-reflection system for psychological awareness.

    Tracks recent thoughts and harmony levels, analyzes trends,
    and generates LLM-powered reflections on the agent's state.

    Supports two modes:
    - Background mode: start()/stop() runs a timer thread, agent reads
      cached reflection via cached_reflection().
    - Synchronous mode: call reflect() directly (for tests).
    """

    def __init__(
        self,
        model: str = "sociopsi-mid",
        event_bus: EventBus | None = None,
        max_thoughts: int = 10,
    ) -> None:
        """Initialize meta-cognition system.

        Args:
            model: Ollama model to use for reflection
            event_bus: Event bus for publishing reflection events
            max_thoughts: Maximum thoughts to track for trend analysis
        """
        self.model = model
        self.event_bus = event_bus or get_event_bus()
        self.max_thoughts = max_thoughts

        # Track recent thoughts and harmony
        self.recent_thoughts: deque[str] = deque(maxlen=max_thoughts)
        self.harmony_history: deque[float] = deque(maxlen=max_thoughts)

        # Subscribe to dialogue events
        self.event_bus.subscribe("dialogue.complete", self._on_dialogue_complete)

        # Cached reflection for background mode
        self._cached_reflection: str = ""
        self._reflection_fresh: bool = False
        self._cache_lock: threading.Lock = threading.Lock()

        # Background thread state
        self._running: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._interval: float = 30.0

        # Context for background reflection (set by agent via update_context)
        self._bg_drive_state: dict[str, dict[str, Any]] = {}
        self._context_lock: threading.Lock = threading.Lock()

    def start(self, interval: float = 30.0) -> None:
        """Start background reflection timer thread.

        Args:
            interval: Seconds between reflection cycles.
        """
        if self._running:
            return
        self._interval = interval
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reflection_loop, name="metacog-bg", daemon=True
        )
        self._thread.start()
        logger.info("MetaCognition background thread started (interval=%.1fs)", interval)

    def stop(self) -> None:
        """Stop background reflection timer thread."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("MetaCognition background thread stopped")

    def update_context(self, drive_state: dict[str, dict[str, Any]]) -> None:
        """Update the drive state used by the background reflection thread."""
        with self._context_lock:
            self._bg_drive_state = drive_state

    def cached_reflection(self) -> str:
        """Read and consume the latest cached reflection.

        Returns the reflection text and marks it as consumed.
        """
        with self._cache_lock:
            text = self._cached_reflection
            if self._reflection_fresh:
                self._reflection_fresh = False
                return text
            return ""

    def _reflection_loop(self) -> None:
        """Background thread: periodically generate reflections."""
        while not self._stop_event.is_set():
            try:
                with self._context_lock:
                    ds = dict(self._bg_drive_state)

                if ds:
                    reflection = self.reflect(ds)
                    if reflection:
                        with self._cache_lock:
                            self._cached_reflection = reflection
                            self._reflection_fresh = True
            except Exception:
                logger.exception("Error in metacognition background loop")

            self._stop_event.wait(self._interval)

    def _on_dialogue_complete(self, data: dict[str, Any]) -> None:
        """Handle dialogue completion event.

        Args:
            data: Event data with mediated_thought and harmony
        """
        thought = data.get("mediated_thought", "")
        harmony = data.get("harmony", 0.5)

        if thought:
            self.recent_thoughts.append(thought)
        self.harmony_history.append(harmony)

    def calculate_harmony_trend(self) -> str:
        """Calculate trend in harmony levels.

        Returns:
            Trend description: "improving", "declining", or "stable"
        """
        if len(self.harmony_history) < 3:
            return "stable"

        history = list(self.harmony_history)

        # Compare recent average to older average
        midpoint = len(history) // 2
        older_avg = sum(history[:midpoint]) / midpoint if midpoint > 0 else 0.5
        recent_avg = sum(history[midpoint:]) / (len(history) - midpoint)

        diff = recent_avg - older_avg

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    def get_average_harmony(self) -> float:
        """Get average harmony level.

        Returns:
            Average harmony (0-1)
        """
        if not self.harmony_history:
            return 0.5
        return sum(self.harmony_history) / len(self.harmony_history)

    def reflect(self, drive_state: dict[str, dict[str, Any]]) -> str:
        """Generate a reflection on current psychological state.

        Args:
            drive_state: Current drive states

        Returns:
            Reflection text
        """
        # Build context for reflection
        thoughts_text = (
            "\n".join(f"- {thought}" for thought in list(self.recent_thoughts)[-5:])
            if self.recent_thoughts
            else "No recent thoughts"
        )

        harmony_trend = self.calculate_harmony_trend()
        avg_harmony = self.get_average_harmony()

        # Summarize drive states
        drive_summary = []
        for name, state in drive_state.items():
            value = state.get("value", 0.5)
            below = state.get("below_threshold", False)
            if below:
                drive_summary.append(f"{name} is low ({value:.2f})")
            elif value > 0.7:
                drive_summary.append(f"{name} is satisfied ({value:.2f})")

        drives_text = ", ".join(drive_summary) if drive_summary else "drives are balanced"

        prompt = f"""You are engaging in meta-cognition - reflecting on your own psychological processes.

Recent thoughts:
{thoughts_text}

Psychological state:
- Harmony trend: {harmony_trend}
- Average harmony: {avg_harmony:.2f}
- Drives: {drives_text}

Reflect briefly (1-2 sentences) on:
- What patterns do you notice in your recent thinking?
- How is your psychological integration progressing?
- What might need attention?

Be introspective and insightful:"""

        try:
            response = chat_with_retry(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.6},
            )
            reflection = response["message"]["content"].strip()

            # Publish reflection event
            self.event_bus.publish(
                "metacognition.reflection",
                {
                    "reflection": reflection,
                    "harmony_trend": harmony_trend,
                    "average_harmony": avg_harmony,
                    "drive_state": drive_state,
                },
            )

            return reflection

        except Exception as e:
            logger.error(f"Error in meta-cognitive reflection: {e}")
            return ""

    def get_state(self) -> dict[str, Any]:
        """Get meta-cognition state.

        Returns:
            State dictionary
        """
        return {
            "recent_thoughts_count": len(self.recent_thoughts),
            "harmony_history_count": len(self.harmony_history),
            "harmony_trend": self.calculate_harmony_trend(),
            "average_harmony": self.get_average_harmony(),
        }
