"""Query handler for state queries."""

from typing import TYPE_CHECKING, Any

from sociopsi.core.event_bus import EventBus

if TYPE_CHECKING:
    from sociopsi.core.agent import SocioPsiAgent


class QueryHandler:
    """Handles state query commands."""

    def __init__(self, event_bus: EventBus, agent: "SocioPsiAgent") -> None:
        """Initialize query handler.

        Args:
            event_bus: Event bus for pub/sub
            agent: SocioPsiAgent instance
        """
        self.event_bus = event_bus
        self.agent = agent

        event_bus.subscribe("command.query", self._on_query_sync)

    def _on_query_sync(self, classification: dict[str, Any]) -> None:
        """Synchronous wrapper for async handler."""
        import asyncio

        asyncio.create_task(self.on_query(classification))

    async def on_query(self, classification: dict[str, Any]) -> None:
        """Handle query command.

        Args:
            classification: Query classification with intent
        """
        intent = classification["intent"].lower()
        params = classification.get("parameters", {})

        # Determine query type
        if "drive" in intent:
            response = self._query_drives()
        elif "thought" in intent or "thinking" in intent:
            response = self._query_thoughts()
        elif "memory" in intent or "remember" in intent:
            response = self._query_memories(params)
        elif "harmony" in intent or "integration" in intent:
            response = self._query_harmony()
        elif "goal" in intent:
            response = self._query_goals()
        else:
            response = self._query_general_state()

        # Publish response
        self.event_bus.publish(
            "command.response", {"text": response, "query": classification["intent"]}
        )

    def _query_drives(self) -> str:
        """Return current drive levels."""
        drives = self.agent.drive_system.drives.values()
        lines = ["Current drives:"]
        for drive in drives:
            status = "✓" if drive.value > drive.base_threshold else "✗"
            lines.append(f"  {status} {drive.name}: {drive.value:.2f}")
        return "\n".join(lines)

    def _query_thoughts(self) -> str:
        """Return recent thoughts."""
        recent = self.agent.memory_system.get_recent_memories(count=3)
        if not recent:
            return "No recent thoughts."
        lines = ["Recent thoughts:"]
        for mem in recent:
            lines.append(f"  - {mem.content}")
        return "\n".join(lines)

    def _query_memories(self, params: dict[str, Any]) -> str:
        """Search memories by query.

        Args:
            params: Parameters dict (may contain 'query')
        """
        query = params.get("query", "")
        if not query:
            return self._query_thoughts()  # Fallback

        # Search will be implemented later with semantic memory
        return self._query_thoughts()

    def _query_harmony(self) -> str:
        """Return current harmony level."""
        harmony = self.agent.dialogue.ego.last_harmony_level
        return f"Harmony: {harmony:.2f}"

    def _query_goals(self) -> str:
        """Return active goals."""
        active = self.agent.goal_manager.get_active_goals()
        if not active:
            return "No active goals."
        lines = ["Active goals:"]
        for goal in active:
            lines.append(f"  - {goal.description} (priority: {goal.priority:.2f})")
        return "\n".join(lines)

    def _query_general_state(self) -> str:
        """General state overview."""
        drives = self._query_drives()
        thoughts = self._query_thoughts()
        return f"{drives}\n\n{thoughts}"
