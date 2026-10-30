import httpx
import pytest

from apyra.auth import OAuth2Client, OAuth2TokenResponse, OIDCTokenValidator, generate_pkce_pair


def test_authorization_url_includes_pkce() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        redirect_uri="https://app.example.com/callback",
        scopes=["openid", "profile"],
    )
    verifier, challenge = generate_pkce_pair()
    url = client.authorization_url(state="state-1", code_challenge=challenge)
    assert "response_type=code" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert verifier != challenge


@pytest.mark.asyncio
async def test_exchange_code_and_refresh() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            import urllib.parse

            data = dict(urllib.parse.parse_qs(request.content.decode()))
            if data.get("grant_type") == ["authorization_code"]:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "access-1",
                        "refresh_token": "refresh-1",
                        "token_type": "Bearer",
                    },
                )
            if data.get("grant_type") == ["refresh_token"]:
                return httpx.Response(
                    200, json={"access_token": "access-2", "token_type": "Bearer"}
                )
        return httpx.Response(404)

    client = OAuth2Client(
        client_id="client",
        client_secret="secret",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(handler),
    )
    exchanged = await client.exchange_code("code-1", code_verifier="verifier")
    assert isinstance(exchanged, OAuth2TokenResponse)
    assert exchanged.access_token == "access-1"
    refreshed = await client.refresh_token("refresh-1")
    assert refreshed.access_token == "access-2"


@pytest.mark.asyncio
async def test_client_credentials_and_revoke() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(
                200, json={"access_token": "service-token", "token_type": "Bearer"}
            )
        if request.url.path == "/revoke":
            return httpx.Response(200)
        return httpx.Response(404)

    client = OAuth2Client(
        client_id="client",
        client_secret="secret",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        revocation_endpoint="https://issuer.example.com/revoke",
        transport=httpx.MockTransport(handler),
    )
    token = await client.client_credentials(scope="read")
    assert token.access_token == "service-token"
    await client.revoke(token.access_token)


@pytest.mark.asyncio
async def test_oidc_token_validator_checks_nonce() -> None:
    class FakeAuthenticator:
        def decode_token(self, token: str):
            return {"header": {}, "payload": {"nonce": "expected-nonce"}}

    validator = OIDCTokenValidator(FakeAuthenticator(), expected_nonce="expected-nonce")
    assert validator.validate("token")["payload"]["nonce"] == "expected-nonce"

    validator = OIDCTokenValidator(FakeAuthenticator(), expected_nonce="wrong")
    with pytest.raises(ValueError):
        validator.validate("token")
