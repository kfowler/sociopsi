"""Tests for memory system."""

import pytest
from time import sleep
from sociopsi.subsystems.memory import Memory, MemorySystem


def test_memory_initialization():
    """Test memory initialization."""
    memory = Memory(content="Test memory", intensity=0.8)

    assert memory.content == "Test memory"
    assert memory.intensity == 0.8
    assert memory.strength == 1.0


def test_memory_decay():
    """Test memory decays over time."""
    memory = Memory(content="Test", intensity=0.5, decay_rate=0.1)

    initial_strength = memory.strength
    memory.decay(dt=1.0)

    assert memory.strength < initial_strength


def test_memory_intensity_slows_decay():
    """Test high-intensity memories decay slower."""
    low_intensity = Memory(content="Low", intensity=0.0, decay_rate=0.1)
    high_intensity = Memory(content="High", intensity=1.0, decay_rate=0.1)

    low_intensity.decay(dt=1.0)
    high_intensity.decay(dt=1.0)

    # High intensity should have decayed less
    assert high_intensity.strength > low_intensity.strength


def test_memory_is_forgotten():
    """Test memory forgotten when below threshold."""
    memory = Memory(content="Test", decay_rate=1.0)

    memory.decay(dt=10.0)  # Decay heavily

    assert memory.is_forgotten(threshold=0.1)


def test_memory_system_initialization():
    """Test memory system initialization."""
    system = MemorySystem(max_memories=50, forget_threshold=0.2)

    assert system.max_memories == 50
    assert system.forget_threshold == 0.2
    assert len(system.memories) == 0


def test_add_memory():
    """Test adding memories."""
    system = MemorySystem()

    system.add_memory("First memory", intensity=0.8)
    system.add_memory("Second memory", intensity=0.5)

    assert len(system.memories) == 2
    assert system.memories[0].content == "First memory"


def test_max_memories_limit():
    """Test max memories limit enforced."""
    system = MemorySystem(max_memories=3)

    system.add_memory("Memory 1", intensity=0.5)
    system.add_memory("Memory 2", intensity=0.7)
    system.add_memory("Memory 3", intensity=0.9)
    system.add_memory("Memory 4", intensity=0.6)  # Should remove weakest

    assert len(system.memories) == 3
    # Weakest (0.5) should be removed
    contents = [m.content for m in system.memories]
    assert "Memory 1" not in contents


def test_memory_system_update():
    """Test memory system update with decay."""
    system = MemorySystem()
    system.add_memory("Test", intensity=0.5, decay_rate=0.1)

    initial_strength = system.memories[0].strength
    system.update(dt=1.0)

    assert system.memories[0].strength < initial_strength


def test_memory_system_forgetting():
    """Test forgotten memories removed."""
    system = MemorySystem(forget_threshold=0.5)

    # Add memory with high decay
    system.add_memory("Forgettable", intensity=0.0, decay_rate=1.0)

    assert len(system.memories) == 1

    # Decay until forgotten
    system.update(dt=10.0)

    assert len(system.memories) == 0


def test_get_recent_memories():
    """Test retrieving recent memories."""
    system = MemorySystem()

    system.add_memory("First")
    sleep(0.01)  # Small delay to ensure different timestamps
    system.add_memory("Second")
    sleep(0.01)
    system.add_memory("Third")

    recent = system.get_recent_memories(count=2)

    assert len(recent) == 2
    assert recent[0].content == "Third"  # Most recent first
    assert recent[1].content == "Second"


def test_get_strong_memories():
    """Test retrieving strongest memories."""
    system = MemorySystem()

    system.add_memory("Weak", intensity=0.3, decay_rate=0.1)
    system.add_memory("Strong", intensity=0.9, decay_rate=0.1)
    system.add_memory("Medium", intensity=0.6, decay_rate=0.1)

    # Decay memories so intensity affects strength
    system.update(dt=1.0)

    strong = system.get_strong_memories(count=2)

    assert len(strong) == 2
    assert strong[0].content == "Strong"  # Strongest first (highest intensity)


def test_get_context():
    """Test formatted context generation."""
    system = MemorySystem()

    system.add_memory("First memory")
    system.add_memory("Second memory")

    context = system.get_context(count=2)

    assert "Recent context:" in context
    assert "First memory" in context
    assert "Second memory" in context
    assert "strength:" in context


def test_get_context_empty():
    """Test context with no memories."""
    system = MemorySystem()

    context = system.get_context()

    assert context == "No recent memories."


def test_get_state():
    """Test getting memory system state."""
    system = MemorySystem()

    system.add_memory("Test 1", intensity=0.8)
    system.add_memory("Test 2", intensity=0.6)

    state = system.get_state()

    assert state["total_memories"] == 2
    assert state["avg_strength"] == pytest.approx(1.0, rel=0.01)
    assert state["strongest_memory"] in ["Test 1", "Test 2"]
