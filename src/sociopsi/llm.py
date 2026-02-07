"""LLM utilities with error handling and retry logic.

Supports two providers:
- "ollama" (default): local inference via ollama
- "anthropic": Anthropic API via ANTHROPIC_API_KEY env var

By default all calls use Ollama. Individual calls can override via the
provider parameter on chat_with_retry(). configure() sets the Anthropic
model name for when it's used.
"""

import logging
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import ollama

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds

# Provider configuration (set via configure())
_anthropic_model: str = "claude-haiku-4-5-20251001"
_log_prompts: bool = False


class LLMError(Exception):
    """Raised when LLM calls fail after retries."""

    pass


def configure(
    anthropic_model: str = "claude-haiku-4-5-20251001",
    log_prompts: bool = False,
) -> None:
    """Configure the LLM settings.

    Args:
        anthropic_model: Anthropic model ID for calls using provider="anthropic".
        log_prompts: If True, print prompts sent to Anthropic and responses.
    """
    global _anthropic_model, _log_prompts
    _anthropic_model = anthropic_model
    _log_prompts = log_prompts
    logger.info(f"Anthropic model: {_anthropic_model}")


def _anthropic_chat(
    messages: Sequence[Mapping[str, Any]],
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Anthropic messages API.

    Translates the ollama-style call into an Anthropic API call and
    normalizes the response to {"message": {"content": str}}.

    Args:
        messages: Chat messages in {"role": ..., "content": ...} format.
        options: Optional dict with "temperature" key.

    Returns:
        Normalized response dict matching ollama format.
    """
    import anthropic

    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    # Separate system message from conversation
    system_text: str | anthropic.NotGiven = anthropic.NOT_GIVEN
    api_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text = str(msg["content"])
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    kwargs: dict[str, Any] = {
        "model": _anthropic_model,
        "messages": api_messages,
        "max_tokens": 1024,
    }
    if system_text is not anthropic.NOT_GIVEN:
        kwargs["system"] = system_text
    if options and "temperature" in options:
        kwargs["temperature"] = options["temperature"]

    if _log_prompts:
        print(f"\n\033[36m{'=' * 60}")
        print(f"[ANTHROPIC PROMPT] model={_anthropic_model}")
        print(f"{'=' * 60}\033[0m")
        if "system" in kwargs:
            print(f"\033[33m[SYSTEM]\033[0m {kwargs['system']}")
        for msg in api_messages:
            color = "\033[32m" if msg["role"] == "user" else "\033[35m"
            print(f"{color}[{msg['role'].upper()}]\033[0m {msg['content']}")
        print(f"\033[36m{'-' * 60}\033[0m")

    response = client.messages.create(**kwargs)
    text = response.content[0].text if response.content else ""

    if _log_prompts:
        print(f"\033[35m[RESPONSE]\033[0m {text}")
        print(f"\033[36m{'=' * 60}\033[0m\n")

    # Normalize to ollama response shape
    return {"message": {"content": text}}


def chat_with_retry(
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_retries: int = MAX_RETRIES,
    options: Mapping[str, Any] | None = None,
    provider: str = "ollama",
) -> Any:
    """Call an LLM provider with exponential backoff retry.

    Args:
        model: The Ollama model name (used when provider is "ollama").
        messages: List of chat messages.
        max_retries: Maximum number of retry attempts.
        options: Optional options (temperature, etc.).
        provider: "ollama" (default) or "anthropic".

    Returns:
        Response dict with {"message": {"content": str}}.

    Raises:
        LLMError: If all retries are exhausted.
    """
    use_anthropic = provider == "anthropic"

    last_error: Exception | None = None
    backoff = INITIAL_BACKOFF

    for attempt in range(max_retries + 1):
        try:
            if use_anthropic:
                return _anthropic_chat(messages, options)
            else:
                kwargs: dict[str, Any] = {"model": model, "messages": messages}
                if options:
                    kwargs["options"] = options
                return ollama.chat(**kwargs)
        except ollama.ResponseError as e:
            last_error = e
            logger.warning(f"Ollama response error (attempt {attempt + 1}/{max_retries + 1}): {e}")
        except ConnectionError as e:
            last_error = e
            logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries + 1}): {e}")
        except TimeoutError as e:
            last_error = e
            logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries + 1}): {e}")
        except Exception as e:
            last_error = e
            logger.warning(f"LLM error (attempt {attempt + 1}/{max_retries + 1}): {e}")

        # Don't sleep after the last attempt
        if attempt < max_retries:
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    provider_name = "Anthropic" if use_anthropic else "Ollama"
    logger.error(f"{provider_name} failed after {max_retries + 1} attempts: {last_error}")
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


# --- Shared ThreadPoolExecutor for offloading LLM calls ---

_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create the shared LLM thread pool executor.

    Lazily initializes a 4-worker pool on first call.

    Returns:
        The shared ThreadPoolExecutor.
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-worker")
    return _executor


def submit_chat(
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_retries: int = MAX_RETRIES,
    options: Mapping[str, Any] | None = None,
    provider: str = "ollama",
) -> Future[Any]:
    """Submit a chat_with_retry call to the thread pool.

    Args:
        model: The model name to use.
        messages: List of chat messages.
        max_retries: Maximum number of retry attempts.
        options: Optional options (temperature, etc.).
        provider: "ollama" (default) or "anthropic".

    Returns:
        A Future that resolves to the chat response.
    """
    return get_executor().submit(chat_with_retry, model, messages, max_retries, options, provider)


def submit_generate_text(
    model: str,
    prompt: str,
    max_retries: int = MAX_RETRIES,
) -> Future[str]:
    """Submit a generate_text call to the thread pool.

    Args:
        model: The model name to use.
        prompt: The user prompt.
        max_retries: Maximum number of retry attempts.

    Returns:
        A Future that resolves to the generated text.
    """
    return get_executor().submit(generate_text, model, prompt, max_retries)


def shutdown_executor(wait: bool = False) -> None:
    """Shut down the shared executor.

    Args:
        wait: Whether to wait for pending futures to complete.
    """
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
