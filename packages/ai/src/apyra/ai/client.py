"""OpenAI-compatible AI client."""

from __future__ import annotations

import ipaddress
from typing import cast
from urllib.parse import urlsplit

import httpx


class AIClient:
    """Async client for OpenAI-compatible chat-completion and embedding APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_insecure_http: bool = False,
    ) -> None:
        try:
            parsed_url = urlsplit(base_url)
            _ = parsed_url.port
        except ValueError as exc:
            raise ValueError("AI base_url is invalid") from exc
        hostname = parsed_url.hostname
        loopback = hostname == "localhost"
        if hostname is not None and not loopback:
            try:
                loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                loopback = False
        if not hostname or parsed_url.scheme not in {"http", "https"}:
            raise ValueError("AI base_url must be an absolute HTTP or HTTPS URL")
        if parsed_url.username is not None or parsed_url.password is not None:
            raise ValueError("AI base_url cannot contain user information")
        if parsed_url.query or parsed_url.fragment or "?" in base_url or "#" in base_url:
            raise ValueError("AI base_url cannot contain a query or fragment")
        if parsed_url.scheme == "http" and not (loopback or allow_insecure_http):
            raise ValueError(
                "AI base_url must use HTTPS unless it targets loopback or allow_insecure_http=True"
            )
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
        """Return the first choice's text for a chat-completion request."""
        client = await self._client_instance()
        response = await client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={"model": model, "messages": messages, "temperature": temperature},
        )
        response.raise_for_status()
        response_data = response.json()
        if not isinstance(response_data, dict):
            raise TypeError("AI response is not an object")
        data = cast(dict[str, object], response_data)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("AI response did not include choices")
        choice = cast(list[object], choices)[0]
        if not isinstance(choice, dict):
            raise TypeError("AI response choice is not an object")
        message = cast(dict[str, object], choice).get("message")
        if not isinstance(message, dict):
            raise TypeError("AI response message is not an object")
        content = cast(dict[str, object], message).get("content")
        if not isinstance(content, str):
            raise TypeError("AI response content is not text")
        return content

    async def embed(self, text: str, *, model: str) -> list[float]:
        """Return the embedding vector for one input string."""
        client = await self._client_instance()
        response = await client.post(
            f"{self._base_url}/embeddings",
            headers=self._headers(),
            json={"model": model, "input": text},
        )
        response.raise_for_status()
        response_data = response.json()
        if not isinstance(response_data, dict):
            raise TypeError("AI response is not an object")
        data = cast(dict[str, object], response_data)
        items = data.get("data")
        if not isinstance(items, list) or not items:
            raise ValueError("AI response did not include embeddings")
        item = cast(list[object], items)[0]
        if not isinstance(item, dict):
            raise TypeError("AI response embedding item is not an object")
        vector = cast(dict[str, object], item).get("embedding")
        if not isinstance(vector, list):
            raise TypeError("AI embedding is not a vector")
        vector_values = cast(list[object], vector)
        if not all(isinstance(value, (int, float, str)) for value in vector_values):
            raise TypeError("AI embedding values must be numeric")
        return [float(value) for value in vector_values if isinstance(value, (int, float, str))]

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release its connections."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
