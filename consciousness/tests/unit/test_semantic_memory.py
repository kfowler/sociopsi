"""Tests for semantic memory."""

import pytest
from time import sleep
from sociopsi.subsystems.semantic_memory import SemanticMemory


def test_semantic_memory_initialization():
    """Test semantic memory initialization."""
    memory = SemanticMemory(max_memories=50, forget_threshold=0.2)

    assert memory.max_memories == 50
    assert memory.forget_threshold == 0.2
    assert len(memory.memories) == 0
    assert len(memory.embeddings) == 0
    assert memory.encoder is not None


def test_add_memory_with_embedding():
    """Test adding memory generates embedding."""
    memory = SemanticMemory()

    memory.add_memory("The cat sat on the mat", intensity=0.8)

    assert len(memory.memories) == 1
    assert len(memory.embeddings) == 1
    assert memory.memories[0].content == "The cat sat on the mat"


def test_add_multiple_memories():
    """Test adding multiple memories."""
    memory = SemanticMemory()

    memory.add_memory("First memory", intensity=0.7)
    memory.add_memory("Second memory", intensity=0.8)
    memory.add_memory("Third memory", intensity=0.6)

    assert len(memory.memories) == 3
    assert len(memory.embeddings) == 3


def test_semantic_search():
    """Test semantic similarity search."""
    memory = SemanticMemory()

    # Add related memories
    memory.add_memory("I love playing with cats", intensity=0.8)
    memory.add_memory("Dogs are great companions", intensity=0.8)
    memory.add_memory("The weather is sunny today", intensity=0.8)

    # Search for cat-related memories
    results = memory.search_similar("Tell me about cats", count=2)

    assert len(results) <= 2
    # Most similar should be the cat memory
    assert "cat" in results[0][0].content.lower()
    # Similarity should be reasonable
    assert results[0][1] > 0.3


def test_semantic_search_empty():
    """Test semantic search with no memories."""
    memory = SemanticMemory()

    results = memory.search_similar("test query")

    assert len(results) == 0


def test_semantic_search_respects_min_strength():
    """Test semantic search filters by minimum strength."""
    memory = SemanticMemory()

    memory.add_memory("Test memory", intensity=0.5)

    # Decay memory heavily
    memory.memories[0].strength = 0.05  # Below default min_strength of 0.1

    results = memory.search_similar("Test", min_strength=0.1)

    assert len(results) == 0


def test_similarity_calculation():
    """Test cosine similarity calculation."""
    memory = SemanticMemory()

    # Add two similar memories
    memory.add_memory("Python is a programming language", intensity=0.8)
    memory.add_memory("Python is used for coding", intensity=0.8)

    results = memory.search_similar("Python programming")

    assert len(results) == 2
    # Both should have decent similarity
    assert results[0][1] > 0.5
    assert results[1][1] > 0.3


def test_update_syncs_embeddings():
    """Test that update keeps embeddings in sync."""
    memory = SemanticMemory(forget_threshold=0.5)

    memory.add_memory("Keep this", intensity=0.9, decay_rate=0.01)
    memory.add_memory("Forget this", intensity=0.1, decay_rate=1.0)

    assert len(memory.memories) == 2
    assert len(memory.embeddings) == 2

    # Decay heavily so second memory is forgotten
    memory.update(dt=10.0)

    # Should have removed forgotten memory and synced embeddings
    assert len(memory.memories) == len(memory.embeddings)


def test_get_context_with_semantic_search():
    """Test getting context with semantic search."""
    memory = SemanticMemory()

    memory.add_memory("User enjoys hiking", intensity=0.8)
    memory.add_memory("User likes programming", intensity=0.8)
    memory.add_memory("User dislikes rain", intensity=0.7)

    context = memory.get_context(query="What outdoor activities?", count=2)

    assert "Relevant memories" in context
    assert "hiking" in context.lower()
    assert "similarity:" in context


def test_get_context_without_query():
    """Test getting context without query uses recent memories."""
    memory = SemanticMemory()

    memory.add_memory("First memory")
    sleep(0.01)
    memory.add_memory("Second memory")
    sleep(0.01)
    memory.add_memory("Third memory")

    context = memory.get_context(count=2)

    assert "Recent context" in context
    assert "Third memory" in context
    assert "Second memory" in context


def test_get_context_no_relevant_memories():
    """Test get context when no relevant memories found."""
    memory = SemanticMemory()

    # Add memory but decay it completely
    memory.add_memory("Test", intensity=0.1, decay_rate=1.0)
    memory.update(dt=10.0)

    context = memory.get_context(query="something")

    assert "No relevant memories" in context


def test_max_memories_with_embeddings():
    """Test that max memories limit works with embeddings."""
    memory = SemanticMemory(max_memories=3)

    memory.add_memory("Memory 1", intensity=0.5)
    memory.add_memory("Memory 2", intensity=0.7)
    memory.add_memory("Memory 3", intensity=0.9)
    memory.add_memory("Memory 4", intensity=0.6)  # Should remove weakest

    assert len(memory.memories) == 3
    assert len(memory.embeddings) == 3
    # Weakest (0.5) should be removed
    contents = [m.content for m in memory.memories]
    assert "Memory 1" not in contents


def test_get_state():
    """Test getting semantic memory state."""
    memory = SemanticMemory()

    memory.add_memory("Test memory")

    state = memory.get_state()

    assert "total_memories" in state
    assert "model" in state
    assert "num_embeddings" in state
    assert state["total_memories"] == 1
    assert state["num_embeddings"] == 1
    assert state["model"] == 384  # all-MiniLM-L6-v2 embedding dimension


def test_cosine_similarity_edge_cases():
    """Test cosine similarity with edge cases."""
    memory = SemanticMemory()

    import numpy as np

    # Test with zero vectors
    zero_vec = np.zeros(384)
    test_vec = np.random.rand(384)

    similarity = memory._cosine_similarity(zero_vec, test_vec)
    assert similarity == 0.0

    # Test with identical vectors
    similarity = memory._cosine_similarity(test_vec, test_vec)
    assert similarity == pytest.approx(1.0, rel=0.01)


def test_search_returns_sorted_by_similarity():
    """Test that search results are sorted by similarity."""
    memory = SemanticMemory()

    memory.add_memory("Cats are feline animals", intensity=0.8)
    memory.add_memory("Dogs are canine animals", intensity=0.8)
    memory.add_memory("Cats love to chase mice", intensity=0.8)

    results = memory.search_similar("Tell me about cats", count=3)

    # Results should be sorted by descending similarity
    for i in range(len(results) - 1):
        assert results[i][1] >= results[i + 1][1]
