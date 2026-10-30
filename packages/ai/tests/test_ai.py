import httpx
import pytest

from apyra.ai import AIClient


@pytest.mark.asyncio
async def test_chat_parses_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    client = AIClient(base_url="https://example.com/v1", transport=httpx.MockTransport(handler))
    assert await client.chat([{"role": "user", "content": "hi"}], model="gpt-test") == "hello"


@pytest.mark.asyncio
async def test_embed_parses_vector() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    client = AIClient(base_url="https://example.com/v1", transport=httpx.MockTransport(handler))
    assert await client.embed("hi", model="embed-test") == [0.1, 0.2]
