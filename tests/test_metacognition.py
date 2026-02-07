"""Tests for the metacognition system and independent timer."""

import time
from unittest.mock import MagicMock, patch

import pytest

from sociopsi.event_bus import EventBus
from sociopsi.metacognition import (
    _AROUSAL_HIGH,
    _AROUSAL_LOW,
    _INTERVAL_FAST,
    _INTERVAL_NORMAL,
    _INTERVAL_SLOW,
    MetaCognition,
    MetacognitionManager,
)


@pytest.fixture(autouse=True)
def _reset_bus():
    EventBus.reset()
    yield
    EventBus.reset()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def metacog(bus: EventBus) -> MetaCognition:
    return MetaCognition(model="test-model", event_bus=bus)


# ---------- MetaCognition unit tests ----------


class TestMetaCognition:
    def test_harmony_trend_stable_with_few_points(self, metacog: MetaCognition):
        metacog.harmony_history.append(0.5)
        assert metacog.calculate_harmony_trend() == "stable"

    def test_harmony_trend_improving(self, metacog: MetaCognition):
        for v in [0.2, 0.2, 0.2, 0.8, 0.8, 0.8]:
            metacog.harmony_history.append(v)
        assert metacog.calculate_harmony_trend() == "improving"

    def test_harmony_trend_declining(self, metacog: MetaCognition):
        for v in [0.8, 0.8, 0.8, 0.2, 0.2, 0.2]:
            metacog.harmony_history.append(v)
        assert metacog.calculate_harmony_trend() == "declining"

    def test_average_harmony_default(self, metacog: MetaCognition):
        assert metacog.get_average_harmony() == 0.5

    def test_average_harmony_computed(self, metacog: MetaCognition):
        metacog.harmony_history.extend([0.4, 0.6])
        assert metacog.get_average_harmony() == pytest.approx(0.5)

    def test_on_dialogue_complete(self, metacog: MetaCognition, bus: EventBus):
        bus.publish("dialogue.complete", {
            "mediated_thought": "Hello",
            "harmony": 0.7,
        })
        assert len(metacog.recent_thoughts) == 1
        assert metacog.harmony_history[-1] == 0.7

    def test_get_state(self, metacog: MetaCognition):
        state = metacog.get_state()
        assert "recent_thoughts_count" in state
        assert "harmony_trend" in state
        assert "average_harmony" in state

    @patch("sociopsi.metacognition.chat_with_retry")
    def test_reflect_publishes_event(self, mock_chat, metacog: MetaCognition, bus: EventBus):
        mock_chat.return_value = {"message": {"content": "A reflection."}}
        received = []
        bus.subscribe("metacognition.reflection", lambda d: received.append(d))

        result = metacog.reflect({"arousal": {"value": 0.5, "below_threshold": False}})

        assert result == "A reflection."
        assert len(received) == 1
        assert received[0]["reflection"] == "A reflection."

    @patch("sociopsi.metacognition.chat_with_retry")
    def test_reflect_handles_error(self, mock_chat, metacog: MetaCognition):
        mock_chat.side_effect = RuntimeError("LLM down")
        result = metacog.reflect({})
        assert result == ""


# ---------- MetacognitionManager tests ----------


def _make_manager(
    bus: EventBus | None = None,
    arousal: float = 0.5,
    reflect_text: str = "test reflection",
) -> tuple[MetacognitionManager, MetaCognition]:
    """Helper to create a manager with mocked reflect."""
    bus = bus or EventBus()
    metacog = MetaCognition(model="test", event_bus=bus)
    metacog.reflect = MagicMock(return_value=reflect_text)  # type: ignore[assignment]
    manager = MetacognitionManager(
        metacognition=metacog,
        drive_state_fn=lambda: {"arousal": {"value": 0.5}},
        arousal_fn=lambda: arousal,
        event_bus=bus,
    )
    return manager, metacog


class TestMetacognitionManager:
    def test_start_stop(self):
        manager, _ = _make_manager()
        manager.start()
        assert manager._thread is not None
        assert manager._thread.is_alive()
        manager.stop()
        assert manager._thread is None

    def test_stop_idempotent(self):
        manager, _ = _make_manager()
        manager.stop()  # Should not raise

    def test_start_idempotent(self):
        manager, _ = _make_manager()
        manager.start()
        thread1 = manager._thread
        manager.start()  # Should not create new thread
        assert manager._thread is thread1
        manager.stop()

    def test_reflection_cached(self):
        manager, metacog = _make_manager()
        manager.start()
        # Wait for at least one reflection cycle
        time.sleep(0.5)
        manager.stop()

        manager.get_latest_reflection()
        # May or may not have run depending on timing, but should not raise
        metacog.reflect.assert_called()  # type: ignore[attr-defined]

    def test_get_latest_reflection_consumes(self):
        manager, _ = _make_manager()
        # Manually set cached reflection
        manager._cached_reflection = "cached text"
        assert manager.get_latest_reflection() == "cached text"
        assert manager.get_latest_reflection() == ""  # Consumed

    def test_suspend_skips_reflection(self):
        manager, metacog = _make_manager()
        manager.suspend()
        manager.start()
        time.sleep(0.3)
        manager.stop()
        # Should not have called reflect while suspended
        metacog.reflect.assert_not_called()  # type: ignore[attr-defined]

    def test_resume_after_suspend(self):
        manager, metacog = _make_manager()
        manager.suspend()
        manager.start()
        time.sleep(0.3)
        metacog.reflect.assert_not_called()  # type: ignore[attr-defined]
        manager.resume()
        # Wait long enough for the suspended check (1s) plus reflection
        time.sleep(1.5)
        manager.stop()
        metacog.reflect.assert_called()  # type: ignore[attr-defined]

    def test_adapt_interval_high_arousal(self):
        manager, _ = _make_manager(arousal=0.9)
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_FAST

    def test_adapt_interval_low_arousal(self):
        manager, _ = _make_manager(arousal=0.1)
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_SLOW

    def test_adapt_interval_normal_arousal(self):
        manager, _ = _make_manager(arousal=0.5)
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_NORMAL

    def test_adapt_interval_boundary_high(self):
        manager, _ = _make_manager(arousal=_AROUSAL_HIGH + 0.01)
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_FAST

    def test_adapt_interval_boundary_low(self):
        manager, _ = _make_manager(arousal=_AROUSAL_LOW - 0.01)
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_SLOW

    def test_reflect_error_does_not_crash_thread(self):
        bus = EventBus()
        metacog = MetaCognition(model="test", event_bus=bus)
        metacog.reflect = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[assignment]
        manager = MetacognitionManager(
            metacognition=metacog,
            drive_state_fn=lambda: {},
            arousal_fn=lambda: 0.5,
            event_bus=bus,
        )
        manager.start()
        time.sleep(0.5)
        # Thread should still be alive despite error
        assert manager._thread is not None
        assert manager._thread.is_alive()
        manager.stop()

    def test_drive_state_fn_error_does_not_crash(self):
        bus = EventBus()
        metacog = MetaCognition(model="test", event_bus=bus)
        metacog.reflect = MagicMock(return_value="ok")  # type: ignore[assignment]
        manager = MetacognitionManager(
            metacognition=metacog,
            drive_state_fn=MagicMock(side_effect=RuntimeError("drive error")),
            arousal_fn=lambda: 0.5,
            event_bus=bus,
        )
        manager.start()
        time.sleep(0.5)
        assert manager._thread is not None
        assert manager._thread.is_alive()
        manager.stop()

    def test_arousal_fn_error_keeps_current_interval(self):
        manager, _ = _make_manager(arousal=0.5)
        manager._interval = _INTERVAL_NORMAL
        # Replace arousal_fn with one that raises
        manager._arousal_fn = MagicMock(side_effect=RuntimeError("no arousal"))
        manager._adapt_interval()
        assert manager._interval == _INTERVAL_NORMAL  # Unchanged
