"""Tests for LLM thread pool executor."""

import time
from concurrent.futures import Future
from unittest.mock import patch

import pytest

from sociopsi.llm import (
    LLMError,
    get_executor,
    shutdown_executor,
    submit_chat,
    submit_generate_text,
)


@pytest.fixture(autouse=True)
def _clean_executor():
    """Ensure executor is shut down between tests."""
    yield
    shutdown_executor(wait=True)


class TestGetExecutor:
    """Tests for get_executor() lazy initialization."""

    def test_returns_thread_pool_executor(self) -> None:
        executor = get_executor()
        assert executor is not None
        assert executor._max_workers == 4

    def test_returns_same_instance(self) -> None:
        executor1 = get_executor()
        executor2 = get_executor()
        assert executor1 is executor2

    def test_recreates_after_shutdown(self) -> None:
        executor1 = get_executor()
        shutdown_executor(wait=True)
        executor2 = get_executor()
        assert executor2 is not None
        assert executor2 is not executor1


class TestSubmitChat:
    """Tests for submit_chat() returning futures."""

    def test_returns_future(self) -> None:
        mock_response = {"message": {"content": "Hello!"}}
        with patch("sociopsi.llm.ollama.chat", return_value=mock_response):
            future = submit_chat(
                model="test",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert isinstance(future, Future)
        assert future.result(timeout=5) == mock_response

    def test_future_propagates_exception(self) -> None:
        with patch("sociopsi.llm.ollama.chat") as mock_chat:
            mock_chat.side_effect = ConnectionError("Always fails")
            with patch("sociopsi.llm.time.sleep"):
                future = submit_chat(
                    model="test",
                    messages=[{"role": "user", "content": "Hi"}],
                    max_retries=0,
                )
                with pytest.raises(LLMError):
                    future.result(timeout=5)


class TestSubmitGenerateText:
    """Tests for submit_generate_text() returning futures."""

    def test_returns_future_with_text(self) -> None:
        mock_response = {"message": {"content": "  Generated text  \n"}}
        with patch("sociopsi.llm.ollama.chat", return_value=mock_response):
            future = submit_generate_text(model="test", prompt="Generate")
        assert isinstance(future, Future)
        assert future.result(timeout=5) == "Generated text"


class TestShutdownExecutor:
    """Tests for shutdown_executor()."""

    def test_shutdown_cleans_up(self) -> None:
        executor = get_executor()
        shutdown_executor(wait=True)
        # After shutdown, _executor should be None (get_executor creates new one)
        new_executor = get_executor()
        assert new_executor is not executor

    def test_shutdown_when_none_is_noop(self) -> None:
        shutdown_executor(wait=True)
        # Should not raise


class TestParallelExecution:
    """Test that parallel submission provides speedup."""

    def test_parallel_faster_than_serial(self) -> None:
        """Four 0.1s tasks should complete in ~0.1s, not ~0.4s."""
        delay = 0.1

        def slow_chat(*args, **kwargs):
            time.sleep(delay)
            return {"message": {"content": "done"}}

        with patch("sociopsi.llm.ollama.chat", side_effect=slow_chat):
            start = time.time()
            futures = [
                submit_chat(model="test", messages=[{"role": "user", "content": f"msg{i}"}])
                for i in range(4)
            ]
            for f in futures:
                f.result(timeout=5)
            elapsed = time.time() - start

        # Should be well under 4x serial time; allow generous margin
        assert elapsed < delay * 2.5, f"Parallel took {elapsed:.2f}s, expected < {delay * 2.5:.2f}s"
