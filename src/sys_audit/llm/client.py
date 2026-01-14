"""Ollama LLM client for code analysis."""

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """Response from LLM analysis."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            prompt: The prompt to send to the model
            system: Optional system prompt
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with the generated content
        """
        client = await self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

            return LLMResponse(
                content=data["message"]["content"],
                model=data.get("model", self.model),
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
            )

        except httpx.ConnectError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama API error: {e.response.text}")

    async def analyze(
        self,
        prompt: str,
        response_format: type[T] | None = None,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> T | dict[str, Any]:
        """Analyze code and return structured output.

        Args:
            prompt: The analysis prompt
            response_format: Optional Pydantic model for structured output
            system: Optional system prompt
            temperature: Sampling temperature

        Returns:
            Parsed response as dict or Pydantic model
        """
        # Add JSON instruction if structured output is expected
        if response_format:
            prompt += "\n\nRespond with valid JSON only, no additional text."

        response = await self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
        )

        content = response.content.strip()

        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                # Find start and end of code block
                start_idx = 1  # Skip first ``` line
                end_idx = len(lines) - 1
                for i, line in enumerate(lines[1:], 1):
                    if line.startswith("```"):
                        end_idx = i
                        break
                content = "\n".join(lines[start_idx:end_idx])

            data = json.loads(content)

            if response_format:
                return response_format.model_validate(data)
            return data

        except json.JSONDecodeError:
            # Return raw content wrapped in a dict
            return {"raw_content": response.content, "parse_error": True}

    async def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            # Check if our model is available
            available_models = [m["name"] for m in data.get("models", [])]

            # Match model name (with or without tag)
            model_base = self.model.split(":")[0]
            return any(
                m.startswith(model_base) for m in available_models
            )
        except Exception:
            return False

    async def ensure_model(self) -> None:
        """Ensure the model is pulled and available."""
        client = await self._get_client()

        try:
            # Try to pull the model (will be fast if already present)
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
                timeout=600,  # Model downloads can take a while
            )
            response.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
