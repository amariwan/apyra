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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [[], {"choices": [None]}, {"choices": [{"message": None}]}],
)
async def test_chat_rejects_malformed_response_shapes(body: object) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = AIClient(base_url="https://example.com/v1", transport=httpx.MockTransport(handler))
    with pytest.raises(TypeError, match="AI response"):
        await client.chat([{"role": "user", "content": "hi"}], model="gpt-test")


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], {"data": [None]}])
async def test_embed_rejects_malformed_response_shapes(body: object) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = AIClient(base_url="https://example.com/v1", transport=httpx.MockTransport(handler))
    with pytest.raises(TypeError, match="AI response"):
        await client.embed("hi", model="embed-test")


def test_ai_client_rejects_plaintext_remote_endpoint_by_default() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AIClient(base_url="http://api.example.com/v1", api_key="secret")


@pytest.mark.parametrize(
    "base_url",
    ["https://user@api.example.com/v1", "https://user:secret@api.example.com/v1"],
)
def test_ai_client_rejects_endpoint_userinfo(base_url: str) -> None:
    with pytest.raises(ValueError, match="user information"):
        AIClient(base_url=base_url, api_key="secret")


@pytest.mark.parametrize("suffix", ["?tenant=one", "#section"])
def test_ai_client_rejects_query_and_fragment_in_base_url(suffix: str) -> None:
    with pytest.raises(ValueError, match="query or fragment"):
        AIClient(base_url=f"https://api.example.com/v1{suffix}")


def test_ai_client_rejects_malformed_endpoint_port() -> None:
    with pytest.raises(ValueError, match="invalid"):
        AIClient(base_url="https://api.example.com:invalid/v1")


def test_ai_client_allows_loopback_http_and_explicit_insecure_opt_in() -> None:
    AIClient(base_url="http://127.0.0.1:8000/v1", api_key="local-key")
    AIClient(base_url="http://api.internal/v1", api_key="local-key", allow_insecure_http=True)
