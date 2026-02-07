"""Tests for the async event bus."""

import threading
import time

import pytest

from sociopsi.event_bus import EventBus


@pytest.fixture(autouse=True)
def _reset_bus():
    """Reset the singleton before and after each test."""
    EventBus.reset()
    yield
    EventBus.reset()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


class TestSynchronousFallback:
    """When dispatcher is not started, publish() dispatches synchronously."""

    def test_basic_publish_subscribe(self, bus: EventBus):
        received = []
        bus.subscribe("test.event", lambda d: received.append(d))
        bus.publish("test.event", {"key": "value"})
        assert received == [{"key": "value"}]

    def test_multiple_subscribers(self, bus: EventBus):
        results_a: list[dict] = []
        results_b: list[dict] = []
        bus.subscribe("test.event", lambda d: results_a.append(d))
        bus.subscribe("test.event", lambda d: results_b.append(d))
        bus.publish("test.event", {"x": 1})
        assert results_a == [{"x": 1}]
        assert results_b == [{"x": 1}]

    def test_no_subscribers_no_error(self, bus: EventBus):
        bus.publish("nonexistent.event", {"x": 1})  # Should not raise

    def test_default_data_is_empty_dict(self, bus: EventBus):
        received = []
        bus.subscribe("test.event", lambda d: received.append(d))
        bus.publish("test.event")
        assert received == [{}]

    def test_unsubscribe(self, bus: EventBus):
        received = []
        handler = lambda d: received.append(d)
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        bus.publish("test.event", {"x": 1})
        assert received == []

    def test_unsubscribe_unknown_handler(self, bus: EventBus):
        bus.unsubscribe("test.event", lambda d: None)  # Should not raise

    def test_clear(self, bus: EventBus):
        received = []
        bus.subscribe("test.event", lambda d: received.append(d))
        bus.clear()
        bus.publish("test.event", {"x": 1})
        assert received == []

    def test_handler_error_does_not_break_others(self, bus: EventBus):
        results: list[dict] = []

        def bad_handler(d: dict) -> None:
            raise ValueError("boom")

        bus.subscribe("test.event", bad_handler)
        bus.subscribe("test.event", lambda d: results.append(d))
        bus.publish("test.event", {"x": 1})
        assert results == [{"x": 1}]

    def test_event_types_are_independent(self, bus: EventBus):
        results_a: list[dict] = []
        results_b: list[dict] = []
        bus.subscribe("type.a", lambda d: results_a.append(d))
        bus.subscribe("type.b", lambda d: results_b.append(d))
        bus.publish("type.a", {"a": 1})
        assert results_a == [{"a": 1}]
        assert results_b == []


class TestAsyncDispatch:
    """When dispatcher is started, publish() enqueues and dispatcher calls handlers."""

    def test_async_dispatch(self, bus: EventBus):
        received = []
        event = threading.Event()
        def handler(d: dict) -> None:
            received.append(d)
            event.set()

        bus.subscribe("test.event", handler)
        bus.start()
        try:
            bus.publish("test.event", {"key": "value"})
            assert event.wait(timeout=2.0), "Handler was not called within timeout"
            assert received == [{"key": "value"}]
        finally:
            bus.stop()

    def test_publish_is_non_blocking(self, bus: EventBus):
        """publish() should return immediately, not wait for handler."""
        handler_started = threading.Event()
        handler_done = threading.Event()

        def slow_handler(d: dict) -> None:
            handler_started.set()
            time.sleep(0.1)
            handler_done.set()

        bus.subscribe("test.event", slow_handler)
        bus.start()
        try:
            start = time.monotonic()
            bus.publish("test.event", {"x": 1})
            publish_time = time.monotonic() - start
            # publish should return well under 100ms (the handler sleep time)
            assert publish_time < 0.05, f"publish() took {publish_time:.3f}s, should be non-blocking"
            # But handler should eventually be called
            assert handler_done.wait(timeout=2.0)
        finally:
            bus.stop()

    def test_ordering_within_event_type(self, bus: EventBus):
        received: list[int] = []
        done = threading.Event()

        def handler(d: dict) -> None:
            received.append(d["seq"])
            if d["seq"] == 4:
                done.set()

        bus.subscribe("test.event", handler)
        bus.start()
        try:
            for i in range(5):
                bus.publish("test.event", {"seq": i})
            assert done.wait(timeout=2.0)
            assert received == [0, 1, 2, 3, 4]
        finally:
            bus.stop()

    def test_drain(self, bus: EventBus):
        received: list[int] = []
        bus.subscribe("test.event", lambda d: received.append(d["v"]))
        bus.start()
        try:
            for i in range(10):
                bus.publish("test.event", {"v": i})
            bus.drain(timeout=2.0)
            assert received == list(range(10))
        finally:
            bus.stop()

    def test_stop_joins_dispatcher(self, bus: EventBus):
        bus.start()
        assert bus._dispatcher is not None
        assert bus._dispatcher.is_alive()
        bus.stop()
        assert bus._dispatcher is None
        assert not bus._running


class TestPriorityEvents:
    """Priority events bypass the queue and dispatch inline."""

    def test_priority_dispatches_inline(self, bus: EventBus):
        received = []
        bus.set_priority("survival.critical")
        bus.subscribe("survival.critical", lambda d: received.append(d))
        bus.start()
        try:
            bus.publish("survival.critical", {"level": "critical"})
            # Should be dispatched already (inline in publish thread)
            assert received == [{"level": "critical"}]
        finally:
            bus.stop()

    def test_priority_before_start(self, bus: EventBus):
        """Priority events still work synchronously when dispatcher not started."""
        received = []
        bus.set_priority("survival.critical")
        bus.subscribe("survival.critical", lambda d: received.append(d))
        bus.publish("survival.critical", {"level": "critical"})
        assert received == [{"level": "critical"}]

    def test_priority_handler_error_does_not_break_others(self, bus: EventBus):
        results: list[dict] = []

        def bad(d: dict) -> None:
            raise RuntimeError("boom")

        bus.set_priority("survival.critical")
        bus.subscribe("survival.critical", bad)
        bus.subscribe("survival.critical", lambda d: results.append(d))
        bus.start()
        try:
            bus.publish("survival.critical", {"x": 1})
            assert results == [{"x": 1}]
        finally:
            bus.stop()


class TestCoalescing:
    """Coalescable events only dispatch the latest value."""

    def test_coalesce_rapid_updates(self, bus: EventBus):
        received: list[dict] = []
        bus.set_coalesce("somatic.update")
        bus.subscribe("somatic.update", lambda d: received.append(d))
        bus.start()
        try:
            # Publish many updates rapidly — only latest should be dispatched
            for i in range(100):
                bus.publish("somatic.update", {"battery": i})
            bus.drain(timeout=2.0)
            # Should have far fewer than 100 dispatches (ideally 1)
            assert len(received) < 100
            # The last dispatched value should be the most recent
            assert received[-1]["battery"] == 99
        finally:
            bus.stop()

    def test_coalesce_before_start(self, bus: EventBus):
        """Without dispatcher, coalescable events fall back to synchronous."""
        received: list[dict] = []
        bus.set_coalesce("somatic.update")
        bus.subscribe("somatic.update", lambda d: received.append(d))
        # Not started — synchronous fallback
        bus.publish("somatic.update", {"battery": 50})
        assert received == [{"battery": 50}]


class TestSingleton:
    """Singleton behavior and reset."""

    def test_get_instance_returns_same(self):
        a = EventBus.get_instance()
        b = EventBus.get_instance()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = EventBus.get_instance()
        EventBus.reset()
        b = EventBus.get_instance()
        assert a is not b

    def test_reset_stops_dispatcher(self):
        bus = EventBus.get_instance()
        bus.start()
        assert bus._running
        EventBus.reset()
        assert not bus._running


class TestMultipleEventTypes:
    """Mixing priority, coalesce, and normal events."""

    def test_mixed_event_types(self, bus: EventBus):
        priority_received: list[dict] = []
        normal_received: list[dict] = []
        coalesce_received: list[dict] = []

        bus.set_priority("survival.critical")
        bus.set_coalesce("somatic.update")

        bus.subscribe("survival.critical", lambda d: priority_received.append(d))
        bus.subscribe("normal.event", lambda d: normal_received.append(d))
        bus.subscribe("somatic.update", lambda d: coalesce_received.append(d))

        bus.start()
        try:
            bus.publish("survival.critical", {"x": 1})
            bus.publish("normal.event", {"y": 2})
            bus.publish("somatic.update", {"z": 3})

            # Priority should be immediate
            assert priority_received == [{"x": 1}]

            # Normal and coalesce need drain
            bus.drain(timeout=2.0)
            assert normal_received == [{"y": 2}]
            assert coalesce_received == [{"z": 3}]
        finally:
            bus.stop()
