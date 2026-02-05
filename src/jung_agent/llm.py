"""LLM utilities with error handling and retry logic."""

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

import ollama

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds


class LLMError(Exception):
    """Raised when LLM calls fail after retries."""

    pass


def chat_with_retry(
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_retries: int = MAX_RETRIES,
    options: Mapping[str, Any] | None = None,
) -> Any:
    """Call ollama.chat with exponential backoff retry.

    Args:
        model: The model name to use.
        messages: List of chat messages (supports ChatMessage TypedDict).
        max_retries: Maximum number of retry attempts.
        options: Optional ollama options (temperature, etc.).

    Returns:
        The response from ollama.chat (ChatResponse type, dict-like).

    Raises:
        LLMError: If all retries are exhausted.
    """
    last_error: Exception | None = None
    backoff = INITIAL_BACKOFF

    # Build kwargs for ollama.chat
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if options:
        kwargs["options"] = options

    for attempt in range(max_retries + 1):
        try:
            response = ollama.chat(**kwargs)
            return response
        except ollama.ResponseError as e:
            last_error = e
            logger.warning(f"Ollama response error (attempt {attempt + 1}/{max_retries + 1}): {e}")
        except ConnectionError as e:
            last_error = e
            logger.warning(
                f"Ollama connection error (attempt {attempt + 1}/{max_retries + 1}): {e}"
            )
        except TimeoutError as e:
            last_error = e
            logger.warning(f"Ollama timeout (attempt {attempt + 1}/{max_retries + 1}): {e}")
        except Exception as e:
            last_error = e
            logger.warning(f"Ollama error (attempt {attempt + 1}/{max_retries + 1}): {e}")

        # Don't sleep after the last attempt
        if attempt < max_retries:
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    logger.error(f"Ollama failed after {max_retries + 1} attempts: {last_error}")
    raise LLMError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")


def generate_text(
    model: str,
    prompt: str,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Generate text using a simple user prompt.

    Args:
        model: The model name to use.
        prompt: The user prompt.
        max_retries: Maximum number of retry attempts.

    Returns:
        The generated text content.

    Raises:
        LLMError: If all retries are exhausted.
    """
    response = chat_with_retry(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_retries=max_retries,
    )
    return response["message"]["content"].strip()
