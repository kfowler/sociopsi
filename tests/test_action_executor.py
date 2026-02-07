"""Tests for parallel-by-category action execution."""

import time
from unittest.mock import patch

import pytest

from sociopsi.actions.executor import (
    ACTION_CATEGORIES,
    CATEGORY_TIMEOUTS,
    DEFAULT_TIMEOUT,
    MAX_PARALLEL_WORKERS,
    PARALLEL_CATEGORIES,
    SEQUENTIAL_CATEGORIES,
    ActionExecutor,
)
from sociopsi.types import Action


@pytest.fixture
def executor(config):
    """Create an ActionExecutor with mocked dependencies."""
    with (
        patch("sociopsi.actions.executor.memory.MemoryStore"),
        patch("sociopsi.actions.executor.memory.Journal"),
        patch("sociopsi.actions.executor.WorldModel.load"),
        patch("sociopsi.actions.executor.creative.set_world_model"),
    ):
        return ActionExecutor(config)


class TestActionCategories:
    """Test that all registered handlers have categories."""

    def test_all_handlers_have_categories(self, executor):
        """Every handler in _handlers should have a category mapping."""
        unmapped = set(executor._handlers.keys()) - set(ACTION_CATEGORIES.keys())
        assert unmapped == set(), f"Actions without categories: {unmapped}"

    def test_all_categories_are_covered(self):
        """All categories should be in either PARALLEL or SEQUENTIAL."""
        all_cats = set(ACTION_CATEGORIES.values())
        covered = PARALLEL_CATEGORIES | set(SEQUENTIAL_CATEGORIES)
        uncovered = all_cats - covered
        assert uncovered == set(), f"Uncovered categories: {uncovered}"

    def test_parallel_and_sequential_disjoint(self):
        """Parallel and sequential categories must not overlap."""
        overlap = PARALLEL_CATEGORIES & set(SEQUENTIAL_CATEGORIES)
        assert overlap == set(), f"Overlapping categories: {overlap}"


class TestExecuteAllEmpty:
    """Test execute_all with no actions."""

    def test_empty_list_returns_empty(self, executor):
        assert executor.execute_all([]) == []


class TestExecuteAllSequential:
    """Test that sequential categories preserve order."""

    def test_communication_runs_in_order(self, executor):
        """Communication actions should execute in submission order."""
        call_order = []

        def mock_speak(**kwargs):
            call_order.append(("speak", kwargs.get("text", "")))
            return {"spoken": True}

        def mock_notify(**kwargs):
            call_order.append(("notify", kwargs.get("message", "")))
            return {"notified": True}

        executor._handlers["speak"] = mock_speak
        executor._handlers["notify"] = mock_notify

        actions = [
            Action(type="speak", params={"text": "first"}),
            Action(type="notify", params={"message": "second"}),
            Action(type="speak", params={"text": "third"}),
        ]
        results = executor.execute_all(actions)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert call_order == [
            ("speak", "first"),
            ("notify", "second"),
            ("speak", "third"),
        ]


class TestExecuteAllParallel:
    """Test that parallel categories run concurrently."""

    def test_parallel_perception_faster_than_serial(self, executor):
        """Multiple perception actions should run concurrently."""
        delay = 0.15

        def slow_check(**kwargs):
            time.sleep(delay)
            return {"status": "ok"}

        executor._handlers["check_battery"] = slow_check
        executor._handlers["check_thermals"] = slow_check
        executor._handlers["check_memory"] = slow_check
        executor._handlers["check_network"] = slow_check

        actions = [
            Action(type="check_battery"),
            Action(type="check_thermals"),
            Action(type="check_memory"),
            Action(type="check_network"),
        ]

        start = time.time()
        results = executor.execute_all(actions)
        elapsed = time.time() - start

        assert len(results) == 4
        assert all(r.success for r in results)
        # 4 tasks at 0.15s each serial = 0.6s. Parallel should be ~0.15s.
        assert elapsed < delay * 2.5, f"Parallel took {elapsed:.2f}s, expected < {delay * 2.5:.2f}s"

    def test_parallel_learning_actions(self, executor):
        """Learning actions should also run in parallel."""
        delay = 0.15

        def slow_fetch(**kwargs):
            time.sleep(delay)
            return {"data": "result"}

        executor._handlers["web_search"] = slow_fetch
        executor._handlers["web_read"] = slow_fetch

        actions = [
            Action(type="web_search", params={"query": "test"}),
            Action(type="web_read", params={"url": "http://example.com"}),
        ]

        start = time.time()
        results = executor.execute_all(actions)
        elapsed = time.time() - start

        assert len(results) == 2
        assert all(r.success for r in results)
        assert elapsed < delay * 2.0, f"Parallel took {elapsed:.2f}s"


class TestExecuteAllMixed:
    """Test mixed parallel + sequential actions."""

    def test_parallel_before_sequential(self, executor):
        """Parallel categories should complete before sequential ones start."""
        events = []

        def perception_handler(**kwargs):
            events.append(("perception_start", time.time()))
            time.sleep(0.1)
            events.append(("perception_end", time.time()))
            return {"ok": True}

        def communication_handler(**kwargs):
            events.append(("communication_start", time.time()))
            return {"ok": True}

        executor._handlers["check_battery"] = perception_handler
        executor._handlers["speak"] = communication_handler

        actions = [
            Action(type="check_battery"),
            Action(type="speak", params={"text": "hello"}),
        ]
        results = executor.execute_all(actions)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Perception should have started before communication
        perception_end = [t for name, t in events if name == "perception_end"][0]
        comm_start = [t for name, t in events if name == "communication_start"][0]
        assert perception_end <= comm_start + 0.05  # small margin for scheduling

    def test_result_order_matches_input_order(self, executor):
        """Results should be in the same order as input actions, regardless of execution order."""
        executor._handlers["check_battery"] = lambda **kw: {"type": "battery"}
        executor._handlers["web_search"] = lambda **kw: {"type": "search"}
        executor._handlers["speak"] = lambda **kw: {"type": "speak"}
        executor._handlers["journal_write"] = lambda **kw: {"type": "journal"}

        actions = [
            Action(type="speak", params={"text": "hi"}),  # sequential
            Action(type="check_battery"),  # parallel
            Action(type="journal_write", params={"entry": "x"}),  # sequential
            Action(type="web_search", params={"query": "q"}),  # parallel
        ]
        results = executor.execute_all(actions)

        assert len(results) == 4
        assert results[0].action_type == "speak"
        assert results[1].action_type == "check_battery"
        assert results[2].action_type == "journal_write"
        assert results[3].action_type == "web_search"


class TestExecuteAllTimeout:
    """Test per-action timeout behavior."""

    def test_slow_action_times_out(self, executor):
        """An action exceeding its timeout should return an error result."""

        def hang(**kwargs):
            time.sleep(60)
            return {"never": "reached"}

        executor._handlers["check_battery"] = hang

        # Override the category timeout to something very short for the test
        with patch.dict("sociopsi.actions.executor.CATEGORY_TIMEOUTS", {"perception": 0.5}):
            actions = [Action(type="check_battery")]
            results = executor.execute_all(actions)

        assert len(results) == 1
        assert not results[0].success
        assert "timed out" in results[0].error

    def test_timeout_doesnt_block_other_actions(self, executor):
        """A timed-out action shouldn't prevent other actions from completing."""

        def hang(**kwargs):
            time.sleep(60)
            return {"never": "reached"}

        def fast(**kwargs):
            return {"fast": True}

        executor._handlers["check_battery"] = hang
        executor._handlers["check_thermals"] = fast

        with patch.dict("sociopsi.actions.executor.CATEGORY_TIMEOUTS", {"perception": 0.5}):
            actions = [
                Action(type="check_battery"),
                Action(type="check_thermals"),
            ]
            results = executor.execute_all(actions)

        assert len(results) == 2
        # Battery should have timed out
        assert not results[0].success
        assert "timed out" in results[0].error
        # Thermals should have succeeded
        assert results[1].success


class TestExecuteAllErrorHandling:
    """Test error handling in parallel execution."""

    def test_exception_in_handler_returns_error_result(self, executor):
        """A handler raising an exception should produce an error ActionResult."""

        def failing_handler(**kwargs):
            raise RuntimeError("sensor offline")

        executor._handlers["check_battery"] = failing_handler

        actions = [Action(type="check_battery")]
        results = executor.execute_all(actions)

        assert len(results) == 1
        assert not results[0].success
        assert "sensor offline" in results[0].error

    def test_unknown_action_in_mixed_batch(self, executor):
        """Unknown actions shouldn't crash the batch."""
        executor._handlers["check_battery"] = lambda **kw: {"ok": True}

        actions = [
            Action(type="check_battery"),
            Action(type="nonexistent_action"),
        ]
        results = executor.execute_all(actions)

        assert len(results) == 2
        assert results[0].success
        assert not results[1].success
        assert "Unknown action type" in results[1].error

    def test_failed_parallel_doesnt_block_sequential(self, executor):
        """A failed parallel action shouldn't prevent sequential actions from running."""

        def failing(**kwargs):
            raise ConnectionError("network down")

        executor._handlers["web_search"] = failing
        executor._handlers["speak"] = lambda **kw: {"spoken": True}

        actions = [
            Action(type="web_search", params={"query": "test"}),
            Action(type="speak", params={"text": "hello"}),
        ]
        results = executor.execute_all(actions)

        assert len(results) == 2
        assert not results[0].success  # web_search failed
        assert results[1].success  # speak still ran


class TestConstants:
    """Test module-level constants are well-formed."""

    def test_max_parallel_workers(self):
        assert MAX_PARALLEL_WORKERS == 4

    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT == 10.0

    def test_all_category_timeouts_positive(self):
        for cat, timeout in CATEGORY_TIMEOUTS.items():
            assert timeout > 0, f"Category {cat} has non-positive timeout"
