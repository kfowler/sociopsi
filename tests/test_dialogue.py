"""Tests for event-driven dialogue manager."""

import threading
import time
from unittest.mock import patch

import pytest

from sociopsi.dialogue import (
    ArchetypalDialogue,
    DialogueManager,
    DialogueResult,
)
from sociopsi.event_bus import EventBus
from sociopsi.types import StreamSegment


@pytest.fixture(autouse=True)
def _reset_bus():
    """Reset the event bus singleton before and after each test."""
    EventBus.reset()
    yield
    EventBus.reset()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


class TestDialogueResult:
    """DialogueResult is a simple dataclass."""

    def test_creation(self):
        result = DialogueResult(
            segments=[StreamSegment(component="persona", text="Hello")],
            mediated_thought="Integrated thought",
            harmony=0.75,
            timestamp=1000.0,
            trigger="speech",
        )
        assert result.harmony == 0.75
        assert result.trigger == "speech"
        assert len(result.segments) == 1
        assert result.mediated_thought == "Integrated thought"


class TestDialogueManager:
    """Tests for the event-driven DialogueManager."""

    @pytest.fixture
    def mock_generate(self):
        """Patch ArchetypalDialogue.generate_dialogue to avoid LLM calls."""
        segments = [StreamSegment(component="persona", text="Test voice")]
        with patch.object(
            ArchetypalDialogue,
            "generate_dialogue",
            return_value=(segments, "Mediated thought", 0.8),
        ) as mock:
            yield mock

    @pytest.fixture
    def manager(self, bus, mock_generate):
        """Create a DialogueManager with mocked dialogue generation."""
        mgr = DialogueManager(model="test-model", event_bus=bus)
        yield mgr
        mgr.stop()

    def test_initial_state_no_cached(self, manager):
        """Before starting, no cached dialogue exists."""
        assert manager.get_cached() is None
        assert manager.is_stale() is True
        assert manager.get_rolling_harmony() == 0.5

    def test_start_stop(self, manager):
        """Manager starts and stops its thread cleanly."""
        manager.start()
        assert manager._running is True
        assert manager._thread is not None
        assert manager._thread.is_alive()

        manager.stop()
        assert manager._running is False

    def test_timer_fallback_generates_dialogue(self, manager, mock_generate):
        """After fallback interval, dialogue is generated without explicit trigger."""
        # Use short fallback for testing
        manager.FALLBACK_INTERVAL = 0.1
        manager.update_state(
            drive_state={"curiosity": {"value": 0.5}},
            context="test context",
        )
        manager.start()

        # Wait for fallback timer to fire
        time.sleep(0.5)

        cached = manager.get_cached()
        assert cached is not None
        assert cached.trigger == "timer_fallback"
        assert cached.mediated_thought == "Mediated thought"
        assert cached.harmony == 0.8
        mock_generate.assert_called()

    def test_event_trigger_generates_dialogue(self, bus, manager, mock_generate):
        """Publishing a trigger event causes dialogue generation."""
        manager.FALLBACK_INTERVAL = 60.0  # Long fallback so only trigger fires
        manager.update_state(
            drive_state={"curiosity": {"value": 0.7}},
            context="speech context",
        )
        manager.start()

        # Publish trigger
        bus.publish("dialogue.trigger", {"reason": "speech"})

        # Wait for generation
        time.sleep(0.5)

        cached = manager.get_cached()
        assert cached is not None
        assert cached.trigger == "speech"

    def test_no_generation_without_state(self, bus, manager, mock_generate):
        """If no state has been set, triggering does not generate."""
        manager.FALLBACK_INTERVAL = 0.1
        manager.start()

        time.sleep(0.3)

        assert manager.get_cached() is None
        mock_generate.assert_not_called()

    def test_rolling_harmony(self, manager, mock_generate):
        """Rolling harmony tracks history of harmony scores."""
        manager.FALLBACK_INTERVAL = 0.05
        manager.update_state(
            drive_state={"curiosity": {"value": 0.5}},
            context="test",
        )
        manager.start()

        # Wait for several generations
        time.sleep(0.5)

        # All generations return 0.8 harmony
        assert manager.get_rolling_harmony() == pytest.approx(0.8)

    def test_rolling_harmony_window(self, manager):
        """Rolling harmony respects window size."""
        # Manually populate history
        with manager._lock:
            manager._harmony_history = [0.5] * 10

        assert manager.get_rolling_harmony() == pytest.approx(0.5)

        # Add more values to exceed window
        with manager._lock:
            manager._harmony_history = [0.5] * 8 + [1.0] * 2

        # Window of 10, so (8*0.5 + 2*1.0) / 10 = 0.6
        assert manager.get_rolling_harmony() == pytest.approx(0.6)

    def test_stale_detection(self, manager):
        """Dialogue becomes stale after STALE_THRESHOLD seconds."""
        # Fresh result
        result = DialogueResult(
            segments=[],
            mediated_thought="test",
            harmony=0.5,
            timestamp=time.time(),
            trigger="test",
        )
        with manager._lock:
            manager._cached = result

        assert manager.is_stale() is False

        # Old result
        old_result = DialogueResult(
            segments=[],
            mediated_thought="old",
            harmony=0.5,
            timestamp=time.time() - 120.0,  # 2 minutes old
            trigger="test",
        )
        with manager._lock:
            manager._cached = old_result

        assert manager.is_stale() is True

    def test_get_state(self, manager):
        """get_state returns combined manager and dialogue state."""
        state = manager.get_state()
        assert "rolling_harmony" in state
        assert "stale" in state
        assert "archetypes" in state  # From underlying dialogue
        assert state["stale"] is True  # No cached dialogue yet

    def test_dialogue_property(self, manager):
        """dialogue property provides access to underlying ArchetypalDialogue."""
        assert isinstance(manager.dialogue, ArchetypalDialogue)

    def test_multiple_triggers_coalesce(self, bus, manager, mock_generate):
        """Rapid triggers don't cause concurrent generations."""
        manager.FALLBACK_INTERVAL = 60.0
        manager.update_state(
            drive_state={"curiosity": {"value": 0.5}},
            context="test",
        )
        manager.start()

        # Fire many triggers rapidly
        for i in range(10):
            bus.publish("dialogue.trigger", {"reason": f"drive:{i}"})

        time.sleep(1.0)

        # Should have generated at least once, but not 10 times
        # (events coalesce via the threading.Event mechanism)
        assert manager.get_cached() is not None
        assert mock_generate.call_count < 10

    def test_generation_error_does_not_crash(self, bus):
        """If generation raises, the manager thread continues."""
        bus_instance = bus
        with patch.object(
            ArchetypalDialogue,
            "generate_dialogue",
            side_effect=[
                ValueError("LLM error"),
                ([StreamSegment(component="persona", text="ok")], "recovered", 0.6),
            ],
        ):
            mgr = DialogueManager(model="test", event_bus=bus_instance)
            mgr.FALLBACK_INTERVAL = 0.1
            mgr.update_state(
                drive_state={"curiosity": {"value": 0.5}},
                context="test",
            )
            mgr.start()

            # Wait for retry
            time.sleep(0.5)

            # Thread should still be alive and eventually succeed
            assert mgr._thread is not None
            assert mgr._thread.is_alive()
            cached = mgr.get_cached()
            if cached is not None:
                assert cached.mediated_thought == "recovered"

            mgr.stop()

    def test_update_state_thread_safe(self, manager):
        """update_state can be called from any thread without issues."""
        errors = []

        def updater(n):
            try:
                for i in range(100):
                    manager.update_state(
                        drive_state={f"drive_{n}": {"value": i / 100}},
                        context=f"context_{n}_{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
