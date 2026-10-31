"""Token issuance, rotation, and revocation helpers."""

from __future__ import annotations

import heapq
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol, cast

import jwt

from .exceptions import AuthenticationError
from .settings import AuthSettings, get_auth_settings


@dataclass(slots=True)
class TokenPair:
    """Access and refresh credentials issued together for one session."""

    access_token: str
    refresh_token: str


class RevocationStore(Protocol):
    """Legacy-compatible revocation operations required by token validation.

    Stores that expire family revocations should track the latest expiry of every linked token.
    The in-memory implementation provides this through an optional registration method.
    """

    def revoke(self, jti: str, expires_at: float | None = None) -> None:
        """Revoke one token identifier, optionally until its expiration time."""
        ...

    def revoke_family(self, family_id: str) -> None:
        """Revoke all tokens associated with a refresh-token family."""
        ...

    def is_revoked(self, jti: str) -> bool:
        """Return whether a token identifier has been revoked."""
        ...

    def is_family_revoked(self, family_id: str) -> bool:
        """Return whether a refresh-token family has been revoked."""
        ...


class InMemoryRevocationStore:
    """Thread-safe revocation store that retains family state through all linked token expiries."""

    def __init__(self) -> None:
        self._revoked: dict[str, float | None] = {}
        self._families: dict[str, float | None] = {}
        self._family_token_expirations: dict[str, float | None] = {}
        self._expirations: list[tuple[float, str, str]] = []
        self._lock = Lock()

    def consume_refresh_token(self, jti: str, family_id: str) -> bool:
        """Atomically consume a refresh token or revoke its family on reuse."""

        with self._lock:
            return self._consume_refresh_token_locked(jti, family_id, None)

    def consume_refresh_token_until(self, jti: str, family_id: str, expires_at: float) -> bool:
        """Consume a refresh token and expire its revocation state with the token."""

        with self._lock:
            return self._consume_refresh_token_locked(jti, family_id, expires_at)

    def _consume_refresh_token_locked(
        self, jti: str, family_id: str, expires_at: float | None
    ) -> bool:
        self._purge_expired_locked(time.time())
        if jti in self._revoked or family_id in self._families:
            if expires_at is None:
                self._set_expiration_locked(self._families, "family", family_id, None)
            else:
                self._revoke_family_until_locked(family_id, expires_at)
            return False
        self._set_expiration_locked(self._revoked, "token", jti, expires_at)
        return True

    def _set_expiration_locked(
        self, entries: dict[str, float | None], kind: str, key: str, expires_at: float | None
    ) -> None:
        if expires_at is not None and expires_at <= time.time():
            return
        if key in entries:
            current_expiration = entries[key]
            if current_expiration is None or expires_at is None or current_expiration >= expires_at:
                return
        entries[key] = expires_at
        if expires_at is not None:
            heapq.heappush(self._expirations, (expires_at, kind, key))

    def _purge_expired_locked(self, now: float) -> None:
        while self._expirations and self._expirations[0][0] <= now:
            expires_at, kind, key = heapq.heappop(self._expirations)
            entries = {
                "token": self._revoked,
                "family": self._families,
                "family_token": self._family_token_expirations,
            }[kind]
            if entries.get(key) == expires_at:
                del entries[key]

    def revoke(self, jti: str, expires_at: float | None = None) -> None:
        """Revoke a token identifier, retaining it until expiration if supplied."""
        with self._lock:
            self._purge_expired_locked(time.time())
            self._set_expiration_locked(self._revoked, "token", jti, expires_at)

    def revoke_family(self, family_id: str) -> None:
        """Revoke a token family without a scheduled expiration."""
        with self._lock:
            self._purge_expired_locked(time.time())
            self._set_expiration_locked(self._families, "family", family_id, None)

    def revoke_family_until(self, family_id: str, expires_at: float) -> None:
        """Revoke a token family until the supplied Unix timestamp."""
        with self._lock:
            self._purge_expired_locked(time.time())
            self._revoke_family_until_locked(family_id, expires_at)

    def register_family_token_expiration(self, family_id: str, expires_at: float) -> None:
        """Track a token expiry so family revocation outlives every family token."""
        with self._lock:
            self._purge_expired_locked(time.time())
            self._set_expiration_locked(
                self._family_token_expirations,
                "family_token",
                family_id,
                expires_at,
            )
            if family_id in self._families:
                self._revoke_family_until_locked(family_id, expires_at)

    def _revoke_family_until_locked(self, family_id: str, expires_at: float) -> None:
        latest_token_expiration = self._family_token_expirations.get(family_id)
        if latest_token_expiration is not None:
            expires_at = max(expires_at, latest_token_expiration)
        self._set_expiration_locked(self._families, "family", family_id, expires_at)

    def is_revoked(self, jti: str) -> bool:
        """Return whether a token identifier is currently revoked."""
        with self._lock:
            self._purge_expired_locked(time.time())
            return jti in self._revoked

    def is_family_revoked(self, family_id: str) -> bool:
        """Return whether a token family is currently revoked."""
        with self._lock:
            self._purge_expired_locked(time.time())
            return family_id in self._families


# Backwards-compatible alias for the earlier blocklist API.
InMemoryTokenBlocklist = InMemoryRevocationStore


class TokenService:
    """Issue, verify, rotate, and revoke signed access and refresh tokens."""

    def __init__(
        self,
        settings: AuthSettings | None = None,
        *,
        store: RevocationStore | None = None,
    ) -> None:
        self._settings = settings or get_auth_settings()
        resolved_store = store if store is not None else InMemoryRevocationStore()
        self._store = resolved_store
        self._legacy_refresh_lock = Lock()

    def _consume_refresh_token(self, jti: str, family_id: str, expires_at: float) -> bool:
        tracks_family_expirations = callable(
            getattr(self._store, "register_family_token_expiration", None)
        )
        consume_until = getattr(self._store, "consume_refresh_token_until", None)
        # Timed consumption is safe only when the store tracks the full family lifetime.
        if tracks_family_expirations and callable(consume_until):
            return cast(bool, consume_until(jti, family_id, self._revocation_deadline(expires_at)))
        consume = getattr(self._store, "consume_refresh_token", None)
        if callable(consume):
            return cast(bool, consume(jti, family_id))

        # Preserve older custom stores; this only serializes refreshes through this service.
        with self._legacy_refresh_lock:
            if self._store.is_revoked(jti) or self._store.is_family_revoked(family_id):
                self._store.revoke_family(family_id)
                return False
            self._store.revoke(jti)
            return True

    def _register_family_token_expiration(self, family_id: str, expires_at: float) -> None:
        register_expiration = getattr(self._store, "register_family_token_expiration", None)
        if callable(register_expiration):
            register_expiration(family_id, self._revocation_deadline(expires_at))

    def _revocation_deadline(self, expires_at: float) -> float:
        """Retain revocation state through the configured JWT expiration leeway."""
        return expires_at + self._settings.clock_skew_secs

    def _secret(self) -> str:
        if self._settings.hs_secret is not None:
            return self._settings.hs_secret.get_secret_value()
        raise AuthenticationError("auth_hs_secret_missing")

    def _now(self) -> int:
        return int(time.time())

    def _identity_claims(self) -> dict[str, str]:
        claims: dict[str, str] = {}
        if self._settings.verify_iss and not self._settings.issuer:
            raise AuthenticationError("issuer_required")
        if self._settings.verify_aud and not self._settings.audience:
            raise AuthenticationError("audience_required")
        if self._settings.issuer:
            claims["iss"] = self._settings.issuer
        if self._settings.audience:
            claims["aud"] = self._settings.audience
        return claims

    def _decode(self, token: str, *, verify_exp: bool = True) -> dict[str, Any]:
        identity_claims = self._identity_claims()
        options = {
            "verify_exp": verify_exp,
            "verify_iss": self._settings.verify_iss,
            "verify_aud": self._settings.verify_aud,
            "require": ["sub", "iat", "exp"],
        }
        kwargs: dict[str, Any] = {"algorithms": ["HS256"], "options": options}
        if self._settings.verify_iss and self._settings.issuer:
            kwargs["issuer"] = identity_claims["iss"]
        else:
            options["verify_iss"] = False
        if self._settings.verify_aud and self._settings.audience:
            kwargs["audience"] = identity_claims["aud"]
        else:
            options["verify_aud"] = False
        return jwt.decode(token, self._secret(), **kwargs)

    def issue_access_token(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        expires_in: int = 900,
        fresh: bool = False,
        family_id: str | None = None,
    ) -> str:
        """Issue a signed access token for a subject with optional scope claims."""
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
        if family_id:
            payload["family"] = family_id
        payload.update(self._identity_claims())
        token = jwt.encode(payload, self._secret(), algorithm="HS256")
        if family_id:
            self._register_family_token_expiration(family_id, float(payload["exp"]))
        return token

    def issue_refresh_token(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        expires_in: int = 3600,
        family_id: str | None = None,
    ) -> str:
        """Issue a refresh token, optionally linked to an existing token family."""
        now = self._now()
        resolved_family_id = family_id or str(uuid.uuid4())
        payload: dict[str, Any] = {
            "sub": subject,
            "type": "refresh",
            "iat": now,
            "exp": now + expires_in,
            "jti": str(uuid.uuid4()),
            "family": resolved_family_id,
            "scopes": scopes or [],
        }
        payload.update(self._identity_claims())
        token = jwt.encode(payload, self._secret(), algorithm="HS256")
        self._register_family_token_expiration(resolved_family_id, float(payload["exp"]))
        return token

    def issue_token_pair(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        access_expires_in: int = 900,
        refresh_expires_in: int = 3600,
        family_id: str | None = None,
    ) -> TokenPair:
        """Issue an access token and its linked refresh token."""
        family = family_id or str(uuid.uuid4())
        return TokenPair(
            access_token=self.issue_access_token(
                subject, scopes=scopes, expires_in=access_expires_in, family_id=family
            ),
            refresh_token=self.issue_refresh_token(
                subject, scopes=scopes, expires_in=refresh_expires_in, family_id=family
            ),
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token and reject reuse of an already consumed token."""
        try:
            payload = self._decode(refresh_token)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("refresh_token_required")
        jti = str(payload.get("jti", ""))
        family_id = str(payload.get("family", ""))
        expires_at = payload.get("exp")
        if (
            not jti
            or not family_id
            or not isinstance(expires_at, (int, float))
            or isinstance(expires_at, bool)
        ):
            raise AuthenticationError("invalid_token")
        if not self._consume_refresh_token(jti, family_id, float(expires_at)):
            raise AuthenticationError("token_reuse_detected")

        subject = str(payload.get("sub", ""))
        scopes = payload.get("scopes")
        valid_scopes: list[str] | None = None
        if "scopes" in payload:
            if not isinstance(scopes, list):
                raise AuthenticationError("invalid_token")
            raw_scopes = cast(list[object], scopes)
            if any(not isinstance(scope, str) for scope in raw_scopes):
                raise AuthenticationError("invalid_token")
            valid_scopes = [scope for scope in raw_scopes if isinstance(scope, str)]
        return self.issue_token_pair(
            subject,
            scopes=valid_scopes,
            family_id=family_id,
        )

    def revoke(self, token: str) -> None:
        """Revoke a token and its family when it is a family-bound refresh token."""
        try:
            payload = self._decode(token, verify_exp=False)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc

        jti = str(payload.get("jti", ""))
        expires_at = payload.get("exp")
        if jti:
            self._store.revoke(
                jti,
                self._revocation_deadline(float(expires_at))
                if isinstance(expires_at, (int, float)) and not isinstance(expires_at, bool)
                else None,
            )
        family_id = payload.get("family")
        if payload.get("type") == "refresh" and isinstance(family_id, str):
            revoke_until = getattr(self._store, "revoke_family_until", None)
            if (
                callable(getattr(self._store, "register_family_token_expiration", None))
                and callable(revoke_until)
                and isinstance(expires_at, (int, float))
                and not isinstance(expires_at, bool)
            ):
                revoke_until(family_id, self._revocation_deadline(float(expires_at)))
            else:
                self._store.revoke_family(family_id)

    def verify_access_token(self, token: str) -> Mapping[str, Any]:
        """Verify an access token and return its decoded claims."""
        try:
            payload = self._decode(token)
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
        """Return the configured revocation store through its legacy property."""
        return self._store

    @property
    def store(self) -> RevocationStore:
        """Return the configured revocation store."""
        return self._store

    def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token and return its replacement pair."""
        return self.refresh(refresh_token)


# Backwards-compatible alias.
TokenIssuer = TokenService


# Backwards-compatible helper.
def rotate_refresh_token(service: TokenService, refresh_token: str) -> TokenPair:
    """Rotate a refresh token through the supplied token service."""
    return service.refresh(refresh_token)
