"""OIDC discovery and OAuth2 introspection helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class OIDCConfiguration:
    issuer: str
    authorization_endpoint: str | None
    token_endpoint: str | None
    userinfo_endpoint: str | None
    revocation_endpoint: str | None
    jwks_uri: str
    scopes_supported: tuple[str, ...]


async def discover_oidc(
    issuer: str,
    *,
    discovery_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout_seconds: float = 10.0,
) -> OIDCConfiguration:
    """Fetch and validate an OpenID Connect discovery document."""

    base = issuer.rstrip("/") + "/"
    url = discovery_url or urljoin(base, ".well-known/openid-configuration")
    import httpx

    async with httpx.AsyncClient(timeout=timeout_seconds, transport=transport) as client:
        response = await client.get(url)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

    discovered_issuer = data.get("issuer")
    if discovered_issuer != issuer:
        raise ValueError("OIDC issuer mismatch")
    jwks_uri = data.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri:
        raise ValueError("OIDC jwks_uri is required")
    scopes = data.get("scopes_supported") or []
    if not isinstance(scopes, list):
        scopes = []
    return OIDCConfiguration(
        issuer=str(discovered_issuer),
        authorization_endpoint=_optional_str(data.get("authorization_endpoint")),
        token_endpoint=_optional_str(data.get("token_endpoint")),
        userinfo_endpoint=_optional_str(data.get("userinfo_endpoint")),
        revocation_endpoint=_optional_str(data.get("revocation_endpoint")),
        jwks_uri=jwks_uri,
        scopes_supported=tuple(str(scope) for scope in scopes),
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


class OAuth2TokenIntrospector:
    """RFC 7662 token introspection client."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        introspection_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._introspection_url = introspection_url
        self._transport = transport
        self._timeout = timeout_seconds

    async def introspect(self, token: str) -> dict[str, Any]:
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode(
            "ascii"
        )
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                self._introspection_url,
                headers={"Authorization": f"Basic {credentials}"},
                data={"token": token},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        return data
