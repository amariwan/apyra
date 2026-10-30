"""Token issuance, rotation, and revocation helpers."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import jwt

from .exceptions import AuthenticationError
from .settings import AuthSettings, get_auth_settings


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


class RevocationStore(Protocol):
    def revoke(self, jti: str, expires_at: float | None = None) -> None: ...

    def revoke_family(self, family_id: str) -> None: ...

    def is_revoked(self, jti: str) -> bool: ...

    def is_family_revoked(self, family_id: str) -> bool: ...


class InMemoryRevocationStore:
    def __init__(self) -> None:
        self._revoked: set[str] = set()
        self._families: set[str] = set()

    def revoke(self, jti: str, expires_at: float | None = None) -> None:
        self._revoked.add(jti)

    def revoke_family(self, family_id: str) -> None:
        self._families.add(family_id)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    def is_family_revoked(self, family_id: str) -> bool:
        return family_id in self._families


# Backwards-compatible alias for the earlier blocklist API.
InMemoryTokenBlocklist = InMemoryRevocationStore


class TokenService:
    def __init__(
        self,
        settings: AuthSettings | None = None,
        *,
        store: RevocationStore | None = None,
    ) -> None:
        self._settings = settings or get_auth_settings()
        self._store = store or InMemoryRevocationStore()

    def _secret(self) -> str:
        if self._settings.hs_secret is not None:
            return self._settings.hs_secret.get_secret_value()
        raise AuthenticationError("auth_hs_secret_missing")

    def _now(self) -> int:
        return int(time.time())

    def issue_access_token(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        expires_in: int = 900,
        fresh: bool = False,
    ) -> str:
        now = self._now()
        payload: dict[str, Any] = {
            "sub": subject,
            "type": "access",
            "iat": now,
            "exp": now + expires_in,
            "jti": str(uuid.uuid4()),
            "fresh": fresh,
            "scopes": scopes or [],
        }
        return jwt.encode(payload, self._secret(), algorithm="HS256")

    def issue_refresh_token(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        expires_in: int = 3600,
        family_id: str | None = None,
    ) -> str:
        now = self._now()
        payload: dict[str, Any] = {
            "sub": subject,
            "type": "refresh",
            "iat": now,
            "exp": now + expires_in,
            "jti": str(uuid.uuid4()),
            "family": family_id or str(uuid.uuid4()),
            "scopes": scopes or [],
        }
        return jwt.encode(payload, self._secret(), algorithm="HS256")

    def issue_token_pair(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        access_expires_in: int = 900,
        refresh_expires_in: int = 3600,
        family_id: str | None = None,
    ) -> TokenPair:
        family = family_id or str(uuid.uuid4())
        return TokenPair(
            access_token=self.issue_access_token(
                subject, scopes=scopes, expires_in=access_expires_in
            ),
            refresh_token=self.issue_refresh_token(
                subject, scopes=scopes, expires_in=refresh_expires_in, family_id=family
            ),
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = jwt.decode(refresh_token, self._secret(), algorithms=["HS256"])
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("refresh_token_required")
        jti = str(payload.get("jti", ""))
        family_id = str(payload.get("family", ""))
        if not jti or not family_id:
            raise AuthenticationError("invalid_token")
        if self._store.is_revoked(jti) or self._store.is_family_revoked(family_id):
            self._store.revoke_family(family_id)
            raise AuthenticationError("token_reuse_detected")

        self._store.revoke(jti)
        subject = str(payload.get("sub", ""))
        scopes = payload.get("scopes")
        return self.issue_token_pair(
            subject,
            scopes=scopes if isinstance(scopes, list) else None,
            family_id=family_id,
        )

    def revoke(self, token: str) -> None:
        try:
            payload = jwt.decode(
                token, self._secret(), algorithms=["HS256"], options={"verify_exp": False}
            )
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc

        jti = str(payload.get("jti", ""))
        if jti:
            self._store.revoke(jti)
        family_id = payload.get("family")
        if payload.get("type") == "refresh" and isinstance(family_id, str):
            self._store.revoke_family(family_id)

    def verify_access_token(self, token: str) -> Mapping[str, Any]:
        try:
            payload = jwt.decode(token, self._secret(), algorithms=["HS256"])
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc
        if payload.get("type") != "access":
            raise AuthenticationError("access_token_required")
        jti = str(payload.get("jti", ""))
        family_id = payload.get("family")
        if jti and self._store.is_revoked(jti):
            raise AuthenticationError("token_revoked")
        if isinstance(family_id, str) and self._store.is_family_revoked(family_id):
            raise AuthenticationError("token_revoked")
        return payload

    @property
    def blocklist(self) -> RevocationStore:
        return self._store

    @property
    def store(self) -> RevocationStore:
        return self._store

    def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        return self.refresh(refresh_token)


# Backwards-compatible alias.
TokenIssuer = TokenService


# Backwards-compatible helper.
def rotate_refresh_token(service: TokenService, refresh_token: str) -> TokenPair:
    return service.refresh(refresh_token)
