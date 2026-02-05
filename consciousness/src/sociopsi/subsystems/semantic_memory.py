"""Semantic memory with vector embeddings for similarity search."""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

from sociopsi.subsystems.memory import Memory, MemorySystem


class SemanticMemory(MemorySystem):
    """Memory system with semantic similarity search using embeddings."""

    def __init__(
        self,
        max_memories: int = 100,
        forget_threshold: float = 0.1,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialize semantic memory.

        Args:
            max_memories: Maximum number of memories to retain
            forget_threshold: Strength threshold for forgetting
            model_name: Sentence transformer model name
        """
        super().__init__(max_memories, forget_threshold)

        # Load sentence transformer model
        # all-MiniLM-L6-v2: lightweight (80MB), fast, good performance
        self.encoder = SentenceTransformer(model_name)
        self.embeddings: list[NDArray[np.float32]] = []

    def add_memory(
        self,
        content: str,
        intensity: float = 0.5,
        decay_rate: float = 0.01,
    ) -> None:
        """Add memory with embedding.

        Args:
            content: Memory content
            intensity: Importance (0-1)
            decay_rate: How fast memory fades
        """
        # Add memory using parent class
        super().add_memory(content, intensity, decay_rate)

        # Generate embedding for the new memory
        embedding = self.encoder.encode(content, convert_to_tensor=False)
        # Ensure it's a numpy array
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding)
        self.embeddings.append(embedding)

        # If we exceeded max_memories, parent class removed the weakest
        # Make sure embeddings stay in sync
        if len(self.embeddings) > len(self.memories):
            # Parent removed a memory, we need to figure out which one
            # Since parent removes the weakest and we don't know which index,
            # rebuild embeddings from scratch
            embeddings = []
            for m in self.memories:
                emb = self.encoder.encode(m.content, convert_to_tensor=False)
                if not isinstance(emb, np.ndarray):
                    emb = np.array(emb)
                embeddings.append(emb)
            self.embeddings = embeddings

    def update(self, dt: float) -> None:
        """Update memories and sync embeddings.

        Args:
            dt: Time delta in seconds
        """
        # Store initial count
        initial_count = len(self.memories)

        # Update using parent class (handles decay and forgetting)
        super().update(dt)

        # If memories were removed, rebuild embeddings
        if len(self.memories) < initial_count:
            embeddings = []
            for m in self.memories:
                emb = self.encoder.encode(m.content, convert_to_tensor=False)
                if not isinstance(emb, np.ndarray):
                    emb = np.array(emb)
                embeddings.append(emb)
            self.embeddings = embeddings

    def search_similar(
        self,
        query: str,
        count: int = 5,
        min_strength: float = 0.1,
    ) -> list[tuple[Memory, float]]:
        """Search for semantically similar memories.

        Args:
            query: Search query
            count: Number of results to return
            min_strength: Minimum memory strength to consider

        Returns:
            List of (memory, similarity_score) tuples, sorted by similarity
        """
        if not self.memories:
            return []

        # Encode query
        query_embedding = self.encoder.encode(query, convert_to_tensor=False)
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.array(query_embedding)

        # Calculate cosine similarities
        similarities = []
        for memory, embedding in zip(self.memories, self.embeddings):
            # Only consider memories above minimum strength
            if memory.strength >= min_strength:
                similarity = self._cosine_similarity(query_embedding, embedding)
                similarities.append((memory, float(similarity)))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top K
        return similarities[:count]

    def get_context(
        self,
        query: str | None = None,
        count: int = 5,
    ) -> str:
        """Get formatted context from memories.

        If query is provided, uses semantic search. Otherwise uses recent memories.

        Args:
            query: Optional search query for semantic search
            count: Number of memories to include

        Returns:
            Formatted context string
        """
        if query:
            # Semantic search
            results = self.search_similar(query, count=count)
            if not results:
                return "No relevant memories found."

            lines = ["Relevant memories:"]
            for memory, similarity in results:
                lines.append(
                    f"- {memory.content} "
                    f"(similarity: {similarity:.2f}, strength: {memory.strength:.2f})"
                )

            return "\n".join(lines)
        else:
            # Fall back to parent class (recent memories)
            return super().get_context(count)

    def _cosine_similarity(self, a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity (0 to 1)
        """
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def get_state(self) -> dict[str, Any]:
        """Get semantic memory system state."""
        base_state = super().get_state()
        base_state["model"] = self.encoder.get_sentence_embedding_dimension()
        base_state["num_embeddings"] = len(self.embeddings)
        return base_state
