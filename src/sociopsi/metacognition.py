"""Meta-cognition system for self-reflection.

Tracks thoughts, analyzes harmony trends, and generates reflections
on the agent's psychological state and processes.

MetacognitionManager runs reflection in its own timer thread, decoupled
from the main agent cycle. Frequency adapts to arousal: faster (15s) under
high arousal, slower (60s) when dormant.
"""

import logging
import threading
from collections import deque
from typing import Any

from sociopsi.event_bus import EventBus, get_event_bus
from sociopsi.llm import chat_with_retry

logger = logging.getLogger(__name__)

# Adaptive interval bounds (seconds)
_INTERVAL_FAST: float = 15.0
_INTERVAL_NORMAL: float = 30.0
_INTERVAL_SLOW: float = 60.0

# Arousal thresholds for interval adaptation
_AROUSAL_HIGH: float = 0.7
_AROUSAL_LOW: float = 0.3


class MetaCognition:
    """Self-reflection system for psychological awareness.

    Tracks recent thoughts and harmony levels, analyzes trends,
    and generates LLM-powered reflections on the agent's state.
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


class MetacognitionManager:
    """Runs metacognition on an independent timer thread.

    Decoupled from the main agent cycle so reflection happens at a
    consistent cadence regardless of cycle speed. The latest reflection
    is cached for the agent to read without waiting.

    Frequency adapts to arousal:
      - High arousal (>0.7): every 15s (need rapid self-monitoring)
      - Normal: every 30s
      - Low arousal / dormant (<0.3): every 60s (conserve resources)
    """

    def __init__(
        self,
        metacognition: MetaCognition,
        drive_state_fn: Any,
        arousal_fn: Any,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the metacognition manager.

        Args:
            metacognition: The MetaCognition instance to run reflections on.
            drive_state_fn: Callable returning current drive state dict.
            arousal_fn: Callable returning current arousal level (0-1 float).
            event_bus: Event bus for subscribing to suspend signals.
        """
        self._metacognition = metacognition
        self._drive_state_fn = drive_state_fn
        self._arousal_fn = arousal_fn
        self._event_bus = event_bus or get_event_bus()

        self._interval: float = _INTERVAL_NORMAL
        self._cached_reflection: str = ""
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._suspended = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the timer thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="metacognition-timer",
        )
        self._thread.start()
        logger.info("MetacognitionManager started (interval=%.0fs)", self._interval)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the timer thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("MetacognitionManager stopped")

    def suspend(self) -> None:
        """Suspend reflection (e.g., Layer 1 thermal critical)."""
        self._suspended = True
        logger.debug("MetacognitionManager suspended")

    def resume(self) -> None:
        """Resume reflection after suspend."""
        self._suspended = False
        logger.debug("MetacognitionManager resumed")

    def get_latest_reflection(self) -> str:
        """Consume the latest cached reflection (non-blocking).

        Returns the most recent reflection and clears the cache so the
        same reflection is not returned twice.

        Returns:
            The most recent reflection text, or empty string if none yet.
        """
        with self._lock:
            result = self._cached_reflection
            self._cached_reflection = ""
            return result

    def _adapt_interval(self) -> None:
        """Adjust reflection interval based on current arousal."""
        try:
            arousal = self._arousal_fn()
        except Exception:
            return

        if arousal > _AROUSAL_HIGH:
            self._interval = _INTERVAL_FAST
        elif arousal < _AROUSAL_LOW:
            self._interval = _INTERVAL_SLOW
        else:
            self._interval = _INTERVAL_NORMAL

    def _run(self) -> None:
        """Timer thread main loop."""
        while not self._stop_event.is_set():
            if self._suspended:
                self._stop_event.wait(timeout=1.0)
                continue

            self._adapt_interval()

            # Run reflection
            try:
                drive_state = self._drive_state_fn()
                reflection = self._metacognition.reflect(drive_state)
                if reflection:
                    with self._lock:
                        self._cached_reflection = reflection
            except Exception as e:
                logger.error("MetacognitionManager reflection error: %s", e)

            # Wait for the adaptive interval (or until stopped)
            self._stop_event.wait(timeout=self._interval)
