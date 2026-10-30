"""OAuth2 and OpenID Connect client helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .oidc import OIDCConfiguration
from urllib.parse import urlencode

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class OAuth2TokenResponse:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OAuth2Client:
    """Small OAuth2/OIDC client for authorization-code and client-credentials flows."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str | None = None,
        authenticator: Any = None,
        authorization_endpoint: str,
        token_endpoint: str,
        revocation_endpoint: str | None = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.authenticator = authenticator
        self.authorization_endpoint = authorization_endpoint
        self.token_endpoint = token_endpoint
        self.revocation_endpoint = revocation_endpoint
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []
        self._transport = transport
        self._timeout = timeout_seconds

    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
        extra_params: dict[str, str] | None = None,
    ) -> str:
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": state,
        }
        if self.redirect_uri:
            params["redirect_uri"] = self.redirect_uri
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        if extra_params:
            params.update(extra_params)
        return f"{self.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, *, code_verifier: str | None = None
    ) -> OAuth2TokenResponse:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
        }
        if self.redirect_uri:
            data["redirect_uri"] = self.redirect_uri
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        return await self._token_request(data)

    async def client_credentials(self, *, scope: str | None = None) -> OAuth2TokenResponse:
        data = {"grant_type": "client_credentials", "client_id": self.client_id}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if scope:
            data["scope"] = scope
        elif self.scopes:
            data["scope"] = " ".join(self.scopes)
        return await self._token_request(data)

    async def refresh_token(
        self, refresh_token: str, *, scope: str | None = None
    ) -> OAuth2TokenResponse:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if scope:
            data["scope"] = scope
        return await self._token_request(data)

    async def revoke(self, token: str, *, token_type_hint: str | None = None) -> None:
        if not self.revocation_endpoint:
            raise ValueError("revocation endpoint is not configured")
        data = {"token": token, "client_id": self.client_id}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if token_type_hint:
            data["token_type_hint"] = token_type_hint
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self.revocation_endpoint, data=data)
            response.raise_for_status()

    async def _token_request(self, data: dict[str, str]) -> OAuth2TokenResponse:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self.token_endpoint, data=data)
            response.raise_for_status()
            raw: dict[str, Any] = response.json()
        return OAuth2TokenResponse(
            access_token=str(raw.get("access_token", "")),
            token_type=str(raw.get("token_type", "Bearer")),
            expires_in=_optional_int(raw.get("expires_in")),
            refresh_token=_optional_str(raw.get("refresh_token")),
            id_token=_optional_str(raw.get("id_token")),
            scope=_optional_str(raw.get("scope")),
            raw=raw,
        )


class OIDCTokenValidator:
    """Validate OIDC ID tokens using Apyra's JWT authenticator."""

    def __init__(self, authenticator: Any, *, expected_nonce: str | None = None) -> None:
        self._authenticator = authenticator
        self._expected_nonce = expected_nonce

    def validate(self, id_token: str) -> Any:
        decoded = self._authenticator.decode_token(id_token)
        payload = decoded["payload"]
        if self._expected_nonce is not None and payload.get("nonce") != self._expected_nonce:
            raise ValueError("OIDC nonce mismatch")
        return decoded


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


class OIDCClient:
    """High-level OpenID Connect client combining discovery and OAuth2 flows."""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str | None = None,
        authenticator: Any = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
        discovery_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.client_secret = client_secret
        self.authenticator = authenticator
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["openid"]
        self.discovery_url = discovery_url
        self._transport = transport
        self._timeout = timeout_seconds
        self._configuration: OIDCConfiguration | None = None
        self._oauth2: OAuth2Client | None = None

    async def discover(self) -> OIDCConfiguration:
        from .oidc import discover_oidc

        if self._configuration is None:
            self._configuration = await discover_oidc(
                self.issuer,
                discovery_url=self.discovery_url,
                transport=self._transport,
                timeout_seconds=self._timeout,
            )
            self._oauth2 = OAuth2Client(
                client_id=self.client_id,
                client_secret=self.client_secret,
                authorization_endpoint=self._configuration.authorization_endpoint or "",
                token_endpoint=self._configuration.token_endpoint or "",
                revocation_endpoint=self._configuration.revocation_endpoint,
                redirect_uri=self.redirect_uri,
                scopes=self.scopes,
                transport=self._transport,
                timeout_seconds=self._timeout,
            )
        return self._configuration

    async def _oauth2_client(self) -> OAuth2Client:
        if self._oauth2 is None:
            await self.discover()
        assert self._oauth2 is not None
        return self._oauth2

    async def authorization_url(
        self, *, state: str, nonce: str | None = None, code_challenge: str | None = None
    ) -> str:
        await self.discover()
        extra = {"nonce": nonce} if nonce else None
        oauth2 = await self._oauth2_client()
        return oauth2.authorization_url(
            state=state, code_challenge=code_challenge, extra_params=extra
        )

    async def exchange_code(
        self, code: str, *, code_verifier: str | None = None, expected_nonce: str | None = None
    ) -> tuple[OAuth2TokenResponse, Any]:
        oauth2 = await self._oauth2_client()
        token_response = await oauth2.exchange_code(code, code_verifier=code_verifier)
        decoded = None
        if token_response.id_token and self.authenticator is not None:
            validator = OIDCTokenValidator(self.authenticator, expected_nonce=expected_nonce)
            decoded = validator.validate(token_response.id_token)
        return token_response, decoded

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        config = await self.discover()
        if not config.userinfo_endpoint:
            raise ValueError("OIDC userinfo endpoint is not available")
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(
                config.userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def refresh_token(
        self, refresh_token: str, *, scope: str | None = None
    ) -> OAuth2TokenResponse:
        oauth2 = await self._oauth2_client()
        return await oauth2.refresh_token(refresh_token, scope=scope)

    async def revoke(self, token: str, *, token_type_hint: str | None = None) -> None:
        oauth2 = await self._oauth2_client()
        await oauth2.revoke(token, token_type_hint=token_type_hint)
