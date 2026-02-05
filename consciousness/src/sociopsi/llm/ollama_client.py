"""Ollama LLM client."""

import json
from collections.abc import AsyncIterator

import httpx


class OllamaClient:
    """Client for Ollama API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2") -> None:
        """Initialize Ollama client.

        Args:
            base_url: Ollama API base URL
            model: Model name to use
        """
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=120.0)  # Increased for large models

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        """Generate completion from prompt.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["response"]

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """Generate completion with streaming.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Generated text chunks
        """
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
