"""Semantic memory with vector embeddings for similarity-based recall.

Memories are stored with intensity-weighted decay - high intensity memories
persist longer. Semantic search allows finding relevant memories by meaning.
"""

import logging
from dataclasses import dataclass, field
from math import exp
from time import time
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Lazy load sentence-transformers to avoid slow startup
_embedding_model: SentenceTransformer | bool | None = None


def get_embedding_model() -> SentenceTransformer | None:
    """Get or create the sentence transformer model (lazy loaded).

    Returns:
        The SentenceTransformer model, or None if unavailable.
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model...")
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence-transformers model loaded")
        except ImportError:
            logger.warning("sentence-transformers not available, semantic search disabled")
            _embedding_model = False
    return _embedding_model if _embedding_model else None  # type: ignore[return-value]


@dataclass
class Memory:
    """A single memory entry with intensity-weighted decay."""

    content: str
    timestamp: float = field(default_factory=time)
    intensity: float = 0.5  # 0.0 to 1.0, higher = more memorable
    emotional_valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    memory_type: str = "thought"  # thought, perception, action, interaction
    embedding: np.ndarray | None = None

    # Decay parameters
    base_decay_rate: float = 0.001  # per second

    def current_strength(self) -> float:
        """Calculate current memory strength after decay.

        High-intensity memories decay more slowly.

        Returns:
            Current strength (0.0 to 1.0)
        """
        elapsed = time() - self.timestamp
        # Higher intensity = slower decay
        effective_decay = self.base_decay_rate * (1.0 - self.intensity * 0.8)
        return self.intensity * exp(-effective_decay * elapsed)

    def is_faded(self, threshold: float = 0.05) -> bool:
        """Check if memory has faded below threshold.

        Args:
            threshold: Minimum strength to keep memory

        Returns:
            True if memory should be forgotten
        """
        return self.current_strength() < threshold


class SemanticMemory:
    """Memory system with semantic search via embeddings.

    Stores memories with intensity-weighted decay and allows
    similarity-based retrieval using sentence embeddings.
    """

    def __init__(
        self,
        max_memories: int = 100,
        forget_threshold: float = 0.05,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialize semantic memory.

        Args:
            max_memories: Maximum number of memories to store
            forget_threshold: Strength threshold below which memories are forgotten
            embedding_model: Name of sentence-transformers model
        """
        self.max_memories = max_memories
        self.forget_threshold = forget_threshold
        self.embedding_model_name = embedding_model
        self.memories: list[Memory] = []
        self._embeddings_dirty = False

    def add_memory(
        self,
        content: str,
        intensity: float = 0.5,
        emotional_valence: float = 0.0,
        memory_type: str = "thought",
    ) -> Memory:
        """Add a new memory.

        Args:
            content: Memory content text
            intensity: How memorable (0-1, higher = persists longer)
            emotional_valence: Emotional tone (-1 to 1)
            memory_type: Type of memory (thought, perception, action, interaction)

        Returns:
            The created Memory object
        """
        memory = Memory(
            content=content,
            intensity=min(1.0, max(0.0, intensity)),
            emotional_valence=emotional_valence,
            memory_type=memory_type,
        )

        # Generate embedding if model available
        model = get_embedding_model()
        if model:
            try:
                embedding = model.encode(content, convert_to_numpy=True)
                memory.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        self.memories.append(memory)

        # Enforce memory limit
        if len(self.memories) > self.max_memories:
            self._forget_weakest()

        return memory

    def update(self, dt: float) -> None:
        """Update memory system, forgetting faded memories.

        Args:
            dt: Time delta in seconds (not used directly, decay is time-based)
        """
        # Remove memories that have faded
        self.memories = [m for m in self.memories if not m.is_faded(self.forget_threshold)]

    def _forget_weakest(self) -> None:
        """Remove the weakest memory when at capacity."""
        if not self.memories:
            return

        # Find memory with lowest current strength
        weakest_idx = min(
            range(len(self.memories)), key=lambda i: self.memories[i].current_strength()
        )
        forgotten = self.memories.pop(weakest_idx)
        logger.debug(f"Forgot memory: {forgotten.content[:50]}...")

    def get_recent(self, count: int = 5) -> list[Memory]:
        """Get most recent memories.

        Args:
            count: Number of memories to return

        Returns:
            List of recent memories, newest first
        """
        sorted_memories = sorted(self.memories, key=lambda m: m.timestamp, reverse=True)
        return sorted_memories[:count]

    def get_strong(self, count: int = 5) -> list[Memory]:
        """Get strongest (most intense/persistent) memories.

        Args:
            count: Number of memories to return

        Returns:
            List of strongest memories
        """
        sorted_memories = sorted(self.memories, key=lambda m: m.current_strength(), reverse=True)
        return sorted_memories[:count]

    def search_similar(self, query: str, count: int = 5) -> list[tuple[Memory, float]]:
        """Search for memories similar to query using embeddings.

        Args:
            query: Search query text
            count: Number of results to return

        Returns:
            List of (memory, similarity_score) tuples, highest similarity first
        """
        model = get_embedding_model()
        if not model:
            # Fall back to recent memories if no embedding model
            return [(m, 1.0) for m in self.get_recent(count)]

        try:
            query_embedding = model.encode(query, convert_to_numpy=True)
        except Exception as e:
            logger.warning(f"Failed to encode query: {e}")
            return [(m, 1.0) for m in self.get_recent(count)]

        # Calculate similarities
        results: list[tuple[Memory, float]] = []
        for memory in self.memories:
            if memory.embedding is not None:
                # Cosine similarity
                similarity = float(
                    np.dot(query_embedding, memory.embedding)
                    / (np.linalg.norm(query_embedding) * np.linalg.norm(memory.embedding))
                )
                results.append((memory, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:count]

    def get_context(self, query: str | None = None, count: int = 3) -> str:
        """Get memory context for dialogue generation.

        Args:
            query: Optional query for semantic search
            count: Number of memories to include

        Returns:
            Formatted context string
        """
        if not self.memories:
            return "No recent memories."

        if query:
            results = self.search_similar(query, count)
            memories = [m for m, _ in results]
        else:
            memories = self.get_recent(count)

        if not memories:
            return "No relevant memories."

        lines = ["Recent memories:"]
        for m in memories:
            strength = m.current_strength()
            lines.append(f"- [{m.memory_type}] {m.content} (strength: {strength:.2f})")

        return "\n".join(lines)

    def get_state(self) -> dict[str, Any]:
        """Get memory system state.

        Returns:
            State dictionary
        """
        return {
            "count": len(self.memories),
            "max_memories": self.max_memories,
            "recent": [m.content[:50] for m in self.get_recent(3)],
            "strong": [m.content[:50] for m in self.get_strong(3)],
        }
