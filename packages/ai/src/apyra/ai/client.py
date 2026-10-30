"""OpenAI-compatible AI client."""

from __future__ import annotations

from typing import Any

import httpx


class AIClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout, transport=self._transport)
        return self._client

    async def chat(
        self, messages: list[dict[str, str]], *, model: str, temperature: float = 0.0
    ) -> str:
        client = await self._client_instance()
        response = await client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={"model": model, "messages": messages, "temperature": temperature},
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("AI response did not include choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise TypeError("AI response content is not text")
        return content

    async def embed(self, text: str, *, model: str) -> list[float]:
        client = await self._client_instance()
        response = await client.post(
            f"{self._base_url}/embeddings",
            headers=self._headers(),
            json={"model": model, "input": text},
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        items = data.get("data") or []
        if not items:
            raise ValueError("AI response did not include embeddings")
        vector = items[0].get("embedding")
        if not isinstance(vector, list):
            raise TypeError("AI embedding is not a vector")
        return [float(value) for value in vector]

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
