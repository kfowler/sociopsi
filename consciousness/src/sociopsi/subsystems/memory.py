"""Memory system with intensity-weighted decay."""

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass
class Memory:
    """A single memory with intensity-weighted decay."""

    content: str
    timestamp: float = field(default_factory=time)
    intensity: float = 1.0  # 0.0 to 1.0, higher = more important
    decay_rate: float = 0.01  # How fast memory fades
    strength: float = 1.0  # Current strength (0.0 to 1.0)

    def decay(self, dt: float) -> None:
        """Decay memory strength over time.

        Intensity slows decay: high-intensity memories fade slower.

        Args:
            dt: Time delta in seconds
        """
        # Effective decay rate reduced by intensity
        effective_decay = self.decay_rate * (1.0 - self.intensity * 0.8)
        self.strength = max(0.0, self.strength - (effective_decay * dt))

    def is_forgotten(self, threshold: float = 0.1) -> bool:
        """Check if memory has decayed below threshold.

        Args:
            threshold: Minimum strength to retain memory

        Returns:
            True if memory should be forgotten
        """
        return self.strength < threshold


class MemorySystem:
    """Manages memories with intensity-weighted decay."""

    def __init__(
        self,
        max_memories: int = 100,
        forget_threshold: float = 0.1,
    ) -> None:
        """Initialize memory system.

        Args:
            max_memories: Maximum number of memories to retain
            forget_threshold: Strength threshold for forgetting
        """
        self.max_memories = max_memories
        self.forget_threshold = forget_threshold
        self.memories: list[Memory] = []

    def add_memory(
        self,
        content: str,
        intensity: float = 0.5,
        decay_rate: float = 0.01,
    ) -> None:
        """Add a new memory.

        Args:
            content: Memory content
            intensity: Importance (0-1, higher = more important)
            decay_rate: How fast memory fades
        """
        memory = Memory(
            content=content,
            intensity=intensity,
            decay_rate=decay_rate,
        )
        self.memories.append(memory)

        # Enforce max memories limit
        if len(self.memories) > self.max_memories:
            # Remove weakest memory
            self.memories.sort(key=lambda m: m.strength)
            self.memories.pop(0)

    def update(self, dt: float) -> None:
        """Update all memories, decaying strength.

        Args:
            dt: Time delta in seconds
        """
        # Decay all memories
        for memory in self.memories:
            memory.decay(dt)

        # Remove forgotten memories
        self.memories = [m for m in self.memories if not m.is_forgotten(self.forget_threshold)]

    def get_recent_memories(self, count: int = 5) -> list[Memory]:
        """Get most recent memories.

        Args:
            count: Number of memories to retrieve

        Returns:
            List of recent memories, sorted by timestamp (newest first)
        """
        sorted_memories = sorted(self.memories, key=lambda m: m.timestamp, reverse=True)
        return sorted_memories[:count]

    def get_strong_memories(self, count: int = 5) -> list[Memory]:
        """Get strongest memories.

        Args:
            count: Number of memories to retrieve

        Returns:
            List of strongest memories
        """
        sorted_memories = sorted(self.memories, key=lambda m: m.strength, reverse=True)
        return sorted_memories[:count]

    def get_context(self, count: int = 5) -> str:
        """Get formatted context from recent memories.

        Args:
            count: Number of memories to include

        Returns:
            Formatted context string
        """
        recent = self.get_recent_memories(count)
        if not recent:
            return "No recent memories."

        lines = ["Recent context:"]
        for memory in recent:
            lines.append(f"- {memory.content} (strength: {memory.strength:.2f})")

        return "\n".join(lines)

    def get_state(self) -> dict[str, Any]:
        """Get memory system state."""
        return {
            "total_memories": len(self.memories),
            "avg_strength": (
                sum(m.strength for m in self.memories) / len(self.memories)
                if self.memories
                else 0.0
            ),
            "strongest_memory": (
                max(self.memories, key=lambda m: m.strength).content if self.memories else None
            ),
        }
