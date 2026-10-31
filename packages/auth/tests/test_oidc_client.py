import time

import httpx
import jwt
import pytest
from pydantic import SecretStr

from apyra.auth import AuthenticationError, AuthSettings, JWTAuthenticator, OIDCClient


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], 0, "not-a-document"])
async def test_oidc_discovery_rejects_non_object_json(payload: object) -> None:
    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(TypeError, match="discovery document must be a JSON object"):
        await client.discover()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], 0, "not-a-userinfo-object"])
async def test_oidc_userinfo_rejects_non_object_json(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example.com",
                    "authorization_endpoint": "https://issuer.example.com/authorize",
                    "token_endpoint": "https://issuer.example.com/token",
                    "jwks_uri": "https://issuer.example.com/jwks",
                    "userinfo_endpoint": "https://issuer.example.com/userinfo",
                },
            )
        return httpx.Response(200, json=payload)

    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TypeError, match="OIDC userinfo response must be a JSON object"):
        await client.userinfo("access-token", expected_subject="user-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"sub": "another-user"}, {"sub": 42}])
async def test_oidc_userinfo_rejects_missing_or_mismatched_subject(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example.com",
                    "authorization_endpoint": "https://issuer.example.com/authorize",
                    "token_endpoint": "https://issuer.example.com/token",
                    "jwks_uri": "https://issuer.example.com/jwks",
                    "userinfo_endpoint": "https://issuer.example.com/userinfo",
                },
            )
        return httpx.Response(200, json=payload)

    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AuthenticationError, match="userinfo_subject_mismatch"):
        await client.userinfo("access-token", expected_subject="user-1")


@pytest.mark.asyncio
async def test_oidc_client_flow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example.com",
                    "authorization_endpoint": "https://issuer.example.com/authorize",
                    "token_endpoint": "https://issuer.example.com/token",
                    "userinfo_endpoint": "https://issuer.example.com/userinfo",
                    "jwks_uri": "https://issuer.example.com/jwks",
                    "revocation_endpoint": "https://issuer.example.com/revoke",
                },
            )
        if path == "/token":
            return httpx.Response(
                200, json={"access_token": "access-1", "id_token": "id-1", "token_type": "Bearer"}
            )
        if path == "/userinfo":
            assert request.headers["authorization"] == "Bearer access-1"
            return httpx.Response(200, json={"sub": "user-1"})
        if path == "/revoke":
            return httpx.Response(200)
        return httpx.Response(404)

    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        client_secret="secret",
        redirect_uri="https://app.example.com/callback",
        transport=httpx.MockTransport(handler),
    )
    config = await client.discover()
    assert config.jwks_uri.endswith("/jwks")

    url = await client.authorization_url(state="state-1", nonce="nonce-1")
    assert "nonce=nonce-1" in url

    token_response, _decoded = await client.exchange_code("code-1")
    assert token_response.access_token == "access-1"
    assert token_response.id_token == "id-1"

    userinfo = await client.userinfo(token_response.access_token, expected_subject="user-1")
    assert userinfo["sub"] == "user-1"

    await client.revoke(token_response.access_token)


@pytest.mark.asyncio
async def test_oidc_missing_token_type_warning_points_to_consumer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example.com",
                    "authorization_endpoint": "https://issuer.example.com/authorize",
                    "token_endpoint": "https://issuer.example.com/token",
                    "jwks_uri": "https://issuer.example.com/jwks",
                },
            )
        return httpx.Response(200, json={"access_token": "access-1", "id_token": "id-1"})

    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        transport=httpx.MockTransport(handler),
    )

    with pytest.warns(DeprecationWarning, match="token_type.*next major") as captured:
        await client.exchange_code("code-1")

    assert len(captured) == 1
    assert captured[0].filename == __file__


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_issuer", "token_audience", "error_code"),
    [
        ("https://issuer.example.com", "client-a", "token_audience_invalid"),
        ("https://other-issuer.example.com", "client-b", "token_issuer_invalid"),
        ("https://issuer.example.com", "client-b", None),
    ],
)
async def test_oidc_client_binds_id_token_to_configured_issuer_and_client(
    token_issuer: str, token_audience: str, error_code: str | None
) -> None:
    issuer = "https://issuer.example.com"
    secret = "synthetic-review-secret-long-enough-for-hs256"
    now = int(time.time())
    id_token = jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 300,
            "iss": token_issuer,
            "aud": token_audience,
        },
        secret,
        algorithm="HS256",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": f"{issuer}/jwks",
                },
            )
        return httpx.Response(
            200,
            json={"access_token": "synthetic-access", "id_token": id_token, "token_type": "Bearer"},
        )

    authenticator = JWTAuthenticator(
        AuthSettings(
            mode="hs",
            hs_secret=SecretStr(secret),
            algorithms=["HS256"],
            issuer=token_issuer,
            audience=token_audience,
        )
    )
    client = OIDCClient(
        issuer=issuer,
        client_id="client-b",
        authenticator=authenticator,
        transport=httpx.MockTransport(handler),
    )

    if error_code is not None:
        with pytest.raises(AuthenticationError, match=error_code):
            await client.exchange_code("synthetic-code")
    else:
        _token_response, decoded = await client.exchange_code("synthetic-code")
        assert decoded["payload"]["aud"] == "client-b"
