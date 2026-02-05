"""Tests for LLM utilities with retry logic."""

from unittest.mock import MagicMock, patch

import pytest

from jung_agent.llm import LLMError, chat_with_retry, generate_text


class TestChatWithRetry:
    """Tests for chat_with_retry function."""

    def test_returns_response_on_success(self) -> None:
        """Test that successful call returns response."""
        mock_response = {"message": {"content": "Hello!"}}

        with patch("jung_agent.llm.ollama.chat", return_value=mock_response):
            result = chat_with_retry(model="test", messages=[{"role": "user", "content": "Hi"}])

        assert result == mock_response

    def test_retries_on_connection_error(self) -> None:
        """Test that connection errors trigger retries."""
        mock_response = {"message": {"content": "Success"}}

        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            # Fail twice, then succeed
            mock_chat.side_effect = [
                ConnectionError("Connection refused"),
                ConnectionError("Connection refused"),
                mock_response,
            ]

            with patch("jung_agent.llm.time.sleep"):  # Don't actually sleep
                result = chat_with_retry(
                    model="test",
                    messages=[{"role": "user", "content": "Hi"}],
                    max_retries=3,
                )

        assert result == mock_response
        assert mock_chat.call_count == 3

    def test_retries_on_timeout_error(self) -> None:
        """Test that timeout errors trigger retries."""
        mock_response = {"message": {"content": "Success"}}

        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            # Fail once, then succeed
            mock_chat.side_effect = [
                TimeoutError("Request timed out"),
                mock_response,
            ]

            with patch("jung_agent.llm.time.sleep"):
                result = chat_with_retry(
                    model="test",
                    messages=[{"role": "user", "content": "Hi"}],
                    max_retries=2,
                )

        assert result == mock_response
        assert mock_chat.call_count == 2

    def test_raises_llm_error_after_max_retries(self) -> None:
        """Test that LLMError is raised after all retries exhausted."""
        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            mock_chat.side_effect = ConnectionError("Always fails")

            with patch("jung_agent.llm.time.sleep"):
                with pytest.raises(LLMError) as exc_info:
                    chat_with_retry(
                        model="test",
                        messages=[{"role": "user", "content": "Hi"}],
                        max_retries=2,
                    )

        assert "LLM call failed after 3 attempts" in str(exc_info.value)
        assert mock_chat.call_count == 3  # Initial + 2 retries

    def test_exponential_backoff(self) -> None:
        """Test that backoff increases exponentially."""
        sleep_times: list[float] = []

        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            mock_chat.side_effect = ConnectionError("Always fails")

            with patch("jung_agent.llm.time.sleep") as mock_sleep:
                mock_sleep.side_effect = lambda t: sleep_times.append(t)

                with pytest.raises(LLMError):
                    chat_with_retry(
                        model="test",
                        messages=[{"role": "user", "content": "Hi"}],
                        max_retries=3,
                    )

        # Should have 3 sleep calls (between attempts, not after last)
        assert len(sleep_times) == 3
        # Initial backoff is 1.0, doubles each time, capped at 10.0
        assert sleep_times[0] == 1.0
        assert sleep_times[1] == 2.0
        assert sleep_times[2] == 4.0

    def test_no_sleep_on_first_attempt(self) -> None:
        """Test that there's no sleep before the first attempt."""
        mock_response = {"message": {"content": "Success"}}

        with patch("jung_agent.llm.ollama.chat", return_value=mock_response):
            with patch("jung_agent.llm.time.sleep") as mock_sleep:
                chat_with_retry(model="test", messages=[{"role": "user", "content": "Hi"}])

        mock_sleep.assert_not_called()

    def test_max_retries_zero_means_one_attempt(self) -> None:
        """Test that max_retries=0 means only one attempt."""
        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            mock_chat.side_effect = ConnectionError("Fails")

            with patch("jung_agent.llm.time.sleep"):
                with pytest.raises(LLMError):
                    chat_with_retry(
                        model="test",
                        messages=[{"role": "user", "content": "Hi"}],
                        max_retries=0,
                    )

        assert mock_chat.call_count == 1


class TestGenerateText:
    """Tests for generate_text function."""

    def test_returns_stripped_content(self) -> None:
        """Test that generate_text returns stripped content."""
        mock_response = {"message": {"content": "  Hello, world!  \n"}}

        with patch("jung_agent.llm.ollama.chat", return_value=mock_response):
            result = generate_text(model="test", prompt="Say hello")

        assert result == "Hello, world!"

    def test_passes_prompt_as_user_message(self) -> None:
        """Test that prompt is passed as user message."""
        mock_response = {"message": {"content": "Response"}}

        with patch("jung_agent.llm.ollama.chat", return_value=mock_response) as mock_chat:
            generate_text(model="test-model", prompt="Test prompt")

        mock_chat.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "Test prompt"}],
        )

    def test_propagates_llm_error(self) -> None:
        """Test that LLMError is propagated from chat_with_retry."""
        with patch("jung_agent.llm.ollama.chat") as mock_chat:
            mock_chat.side_effect = ConnectionError("Fails")

            with patch("jung_agent.llm.time.sleep"):
                with pytest.raises(LLMError):
                    generate_text(model="test", prompt="Test", max_retries=0)


class TestLLMError:
    """Tests for LLMError exception."""

    def test_is_exception(self) -> None:
        """Test that LLMError is an Exception."""
        assert issubclass(LLMError, Exception)

    def test_can_be_raised_with_message(self) -> None:
        """Test that LLMError can be raised with a message."""
        with pytest.raises(LLMError) as exc_info:
            raise LLMError("Test error message")

        assert str(exc_info.value) == "Test error message"
