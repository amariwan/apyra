"""Authorization policies for Apyra."""

from __future__ import annotations

import heapq
import threading
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import uuid4

from .roles import extract_roles, extract_scopes

_MISSING = object()


def _empty_object_dict() -> dict[str, Any]:
    return {}


class Policy(Protocol):
    """A policy that can allow or deny an action."""

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return whether the principal may perform the action."""
        ...


class RolePolicy:
    """Map roles to permissions and evaluate role-based access."""

    def __init__(self, role_permissions: Mapping[str, set[str] | frozenset[str]]) -> None:
        self._role_permissions = {
            str(role).lower(): frozenset(permission.lower() for permission in permissions)
            for role, permissions in role_permissions.items()
        }

    def permissions_for(self, principal: Mapping[str, Any]) -> frozenset[str]:
        """Collect permissions granted to the principal's roles."""
        permissions: set[str] = set()
        for role in extract_roles(dict(principal)):
            permissions.update(self._role_permissions.get(role.lower(), frozenset()))
        return frozenset(permissions)

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Check whether a role grants the requested action or wildcard."""
        normalized_action = action.lower()
        permissions = self.permissions_for(principal)
        return (
            normalized_action in permissions
            or "*" in permissions
            or f"{normalized_action.split(':', 1)[0]}:*" in permissions
        )


class ScopePolicy:
    """Evaluate OAuth2/OIDC scopes as permissions."""

    def __init__(self, *, scope_claim: str = "scopes") -> None:
        self._scope_claim = scope_claim

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Check whether the principal's configured scope claim includes the action."""
        scopes = extract_scopes(dict(principal), claim=self._scope_claim)
        normalized_action = action.lower()
        return normalized_action in {scope.lower() for scope in scopes} or "*" in scopes


class AllOfPolicy:
    """Allow only when every child policy allows."""

    def __init__(self, *policies: Policy) -> None:
        if not policies:
            raise ValueError("AllOfPolicy requires at least one policy")
        self._policies = policies

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return true only when every child policy allows the action."""
        return all(policy.allows(principal, action, resource, context) for policy in self._policies)


class AnyOfPolicy:
    """Allow when at least one child policy allows."""

    def __init__(self, *policies: Policy) -> None:
        self._policies = policies

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return true when any child policy allows the action."""
        return any(policy.allows(principal, action, resource, context) for policy in self._policies)


class PolicyEngine:
    """Evaluate a set of authorization policies."""

    def __init__(self, *policies: Policy) -> None:
        self._policies = policies

    def is_allowed(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return whether all configured policies allow the action."""
        if not self._policies:
            return False
        return all(policy.allows(principal, action, resource, context) for policy in self._policies)

    def authorize(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """Raise ``AuthorizationError`` when the configured policies deny access."""
        from .exceptions import AuthorizationError

        if not self.is_allowed(principal, action, resource, context):
            raise AuthorizationError(f"not_authorized:{action}")


class AttributePolicy:
    """Evaluate attribute-based access-control rules.

    ``conditions`` maps a dotted attribute path to either an expected value or
    a predicate. Paths are resolved from ``principal``, ``resource``, and
    ``context``.
    """

    def __init__(self, conditions: Mapping[str, Any]) -> None:
        if not conditions:
            raise ValueError("AttributePolicy requires at least one condition")
        self._conditions = dict(conditions)

    @staticmethod
    def _resolve(
        path: str, principal: Mapping[str, Any], resource: Any, context: Mapping[str, Any] | None
    ) -> object:
        current: object
        if path.startswith("principal."):
            current = principal
            parts = path.split(".")[1:]
        elif path.startswith("resource."):
            current = resource
            parts = path.split(".")[1:]
        elif path.startswith("context."):
            current = context or {}
            parts = path.split(".")[1:]
        else:
            current = {"principal": principal, "resource": resource, "context": context or {}}
            parts = path.split(".")

        for part in parts:
            if isinstance(current, Mapping):
                values = cast(Mapping[str, object], current)
                if part not in values:
                    return _MISSING
                current = values[part]
            else:
                current = cast(object, getattr(current, part, _MISSING))
                if current is _MISSING:
                    return _MISSING
        return current

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Evaluate every configured path/value or path/predicate condition."""
        for path, expected in self._conditions.items():
            value = self._resolve(path, principal, resource, context)
            if value is _MISSING:
                return False
            if callable(expected):
                if not bool(expected(value)):
                    return False
            elif value != expected:
                return False
        return True


@dataclass
class Session:
    """A server-side authentication session."""

    session_id: str
    principal: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    metadata: dict[str, Any] = field(default_factory=_empty_object_dict)

    @property
    def is_expired(self) -> bool:
        """Return whether the session expiry time has passed in UTC."""
        return datetime.now(UTC) >= self.expires_at


@dataclass
class SessionStore(Protocol):
    """Storage contract for server-side authentication sessions."""

    def create(
        self,
        principal: Mapping[str, Any],
        *,
        ttl_seconds: int = 3600,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        """Create a session with an independent copy of principal data."""
        ...

    def get(self, session_id: str) -> Session | None:
        """Return an active session, or ``None`` when absent or expired."""
        ...

    def revoke(self, session_id: str) -> None:
        """Remove a session so it cannot be retrieved again."""
        ...


class InMemorySessionStore:
    """Thread-safe in-memory session store with expiry."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._expirations: list[tuple[datetime, str]] = []
        self._lock = threading.Lock()

    def create(
        self,
        principal: Mapping[str, Any],
        *,
        ttl_seconds: int = 3600,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        """Create a session and return a copy isolated from stored state."""
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        now = datetime.now(UTC)
        session = Session(
            session_id=uuid4().hex,
            principal=deepcopy(dict(principal)),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            metadata=deepcopy(dict(metadata or {})),
        )
        with self._lock:
            self._purge_expired_locked(now)
            self._sessions[session.session_id] = session
            heapq.heappush(self._expirations, (session.expires_at, session.session_id))
            return deepcopy(session)

    def get(self, session_id: str) -> Session | None:
        """Return a copy of an active session, or ``None`` if unavailable."""
        with self._lock:
            self._purge_expired_locked(datetime.now(UTC))
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return deepcopy(session)

    def revoke(self, session_id: str) -> None:
        """Remove the session identified by ``session_id`` if it exists."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Remove expired sessions and return the number removed."""
        now = datetime.now(UTC)
        with self._lock:
            return self._purge_expired_locked(now)

    def _purge_expired_locked(self, now: datetime) -> int:
        expired_count = 0
        while self._expirations and self._expirations[0][0] <= now:
            expires_at, session_id = heapq.heappop(self._expirations)
            session = self._sessions.get(session_id)
            if session is not None and session.expires_at == expires_at:
                del self._sessions[session_id]
                expired_count += 1
        return expired_count


__all__ = [
    "AllOfPolicy",
    "AnyOfPolicy",
    "AttributePolicy",
    "InMemorySessionStore",
    "Policy",
    "PolicyEngine",
    "RolePolicy",
    "ScopePolicy",
    "Session",
    "SessionStore",
]
