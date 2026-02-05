"""Meta-cognition - reflection on thoughts and processes."""

from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient


class MetaCognition:
    """Meta-cognitive reflection on thoughts and internal processes."""

    def __init__(
        self,
        event_bus: EventBus,
        llm_client: OllamaClient,
        max_thoughts: int = 5,
    ) -> None:
        """Initialize meta-cognition system.

        Args:
            event_bus: Event bus for subscribing to thoughts
            llm_client: LLM client for generating reflections
            max_thoughts: Maximum number of recent thoughts to track
        """
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.max_thoughts = max_thoughts
        self.recent_thoughts: list[dict[str, Any]] = []

        # Subscribe to dialogue completion events
        self.event_bus.subscribe("dialogue.complete", self._on_thought)

    def _on_thought(self, data: dict[str, Any]) -> None:
        """Track recent thoughts from dialogue system.

        Args:
            data: Event data containing mediated thought and harmony
        """
        thought_record = {
            "thought": data.get("mediated_thought", ""),
            "harmony": data.get("harmony", 0.5),
            "archetypal_voices": data.get("archetypal_voices", {}),
        }

        self.recent_thoughts.append(thought_record)

        # Keep only most recent thoughts
        if len(self.recent_thoughts) > self.max_thoughts:
            self.recent_thoughts.pop(0)

    async def reflect(self, drive_state: dict[str, dict[str, Any]]) -> str:
        """Generate meta-cognitive reflection.

        Reflects on recent thought patterns, drive states, and psychological integration.

        Args:
            drive_state: Current drive states

        Returns:
            Meta-cognitive reflection text
        """
        if not self.recent_thoughts:
            return "No thoughts to reflect upon yet."

        # Build summary of recent thoughts
        thoughts_summary = self._summarize_thoughts()

        # Build drive summary
        drive_summary = self._summarize_drives(drive_state)

        # Calculate harmony trend
        harmony_trend = self._calculate_harmony_trend()

        # Build reflection prompt
        prompt = f"""You are engaging in meta-cognition - reflecting on your own thought processes and internal state.

Recent thoughts ({len(self.recent_thoughts)}):
{thoughts_summary}

Current drives:
{drive_summary}

Harmony trend: {harmony_trend}

Reflect on:
1. What patterns do you notice in your thoughts?
2. Are your drives being satisfied or frustrated?
3. How is your psychological integration (harmony levels)?
4. What might you need to focus on?

Provide a brief (2-3 sentences) meta-cognitive reflection:"""

        # Generate reflection
        reflection = await self.llm_client.generate(
            prompt,
            temperature=0.7,
            max_tokens=150,
        )

        reflection_text = reflection.strip()

        # Publish meta-cognition event
        self.event_bus.publish(
            "metacognition.reflection",
            {
                "reflection": reflection_text,
                "drive_state": drive_state,
                "thought_count": len(self.recent_thoughts),
                "harmony_trend": harmony_trend,
            },
        )

        return reflection_text

    def _summarize_thoughts(self) -> str:
        """Summarize recent thoughts.

        Returns:
            Formatted summary string
        """
        lines = []
        for i, record in enumerate(self.recent_thoughts, 1):
            thought = record["thought"]
            harmony = record["harmony"]
            # Truncate long thoughts
            if len(thought) > 80:
                thought = thought[:77] + "..."
            lines.append(f"{i}. {thought} (harmony: {harmony:.2f})")

        return "\n".join(lines)

    def _summarize_drives(self, drive_state: dict[str, dict[str, Any]]) -> str:
        """Summarize current drive states.

        Args:
            drive_state: Current drive states

        Returns:
            Formatted summary string
        """
        lines = []
        for name, state in drive_state.items():
            value = state["value"]
            below_threshold = state["below_threshold"]
            status = "needs attention" if below_threshold else "satisfied"
            lines.append(f"- {name}: {value:.2f} ({status})")

        return "\n".join(lines)

    def _calculate_harmony_trend(self) -> str:
        """Calculate trend in harmony levels.

        Returns:
            Trend description (improving, declining, stable)
        """
        if len(self.recent_thoughts) < 2:
            return "insufficient data"

        harmonies = [t["harmony"] for t in self.recent_thoughts]

        # Compare first half vs second half
        mid = len(harmonies) // 2
        first_half_avg = sum(harmonies[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(harmonies[mid:]) / (len(harmonies) - mid)

        diff = second_half_avg - first_half_avg

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    def get_state(self) -> dict[str, Any]:
        """Get meta-cognition system state.

        Returns:
            State dictionary
        """
        harmonies = [t["harmony"] for t in self.recent_thoughts]
        avg_harmony = sum(harmonies) / len(harmonies) if harmonies else 0.0

        return {
            "thought_count": len(self.recent_thoughts),
            "avg_harmony": avg_harmony,
            "harmony_trend": self._calculate_harmony_trend(),
        }

    def clear_thoughts(self) -> None:
        """Clear recent thoughts history."""
        self.recent_thoughts.clear()
