"""Authorization policies for Apyra."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from .roles import extract_roles, extract_scopes


class Policy(Protocol):
    """A policy that can allow or deny an action."""

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool: ...


class RolePolicy:
    """Map roles to permissions and evaluate role-based access."""

    def __init__(self, role_permissions: Mapping[str, set[str] | frozenset[str]]) -> None:
        self._role_permissions = {
            str(role).lower(): frozenset(permission.lower() for permission in permissions)
            for role, permissions in role_permissions.items()
        }

    def permissions_for(self, principal: Mapping[str, Any]) -> frozenset[str]:
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
        scopes = extract_scopes(dict(principal), claim=self._scope_claim)
        normalized_action = action.lower()
        return normalized_action in {scope.lower() for scope in scopes} or "*" in scopes


class AllOfPolicy:
    """Allow only when every child policy allows."""

    def __init__(self, *policies: Policy) -> None:
        self._policies = policies

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
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
        self._conditions = dict(conditions)

    @staticmethod
    def _resolve(
        path: str, principal: Mapping[str, Any], resource: Any, context: Mapping[str, Any] | None
    ) -> Any:
        current: Any
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
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    def allows(
        self,
        principal: Mapping[str, Any],
        action: str,
        resource: Any = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        for path, expected in self._conditions.items():
            value = self._resolve(path, principal, resource, context)
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
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at


@dataclass
class SessionStore(Protocol):
    def create(
        self,
        principal: Mapping[str, Any],
        *,
        ttl_seconds: int = 3600,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session: ...

    def get(self, session_id: str) -> Session | None: ...

    def revoke(self, session_id: str) -> None: ...


class InMemorySessionStore:
    """Thread-safe in-memory session store with expiry."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(
        self,
        principal: Mapping[str, Any],
        *,
        ttl_seconds: int = 3600,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        now = datetime.now(UTC)
        session = Session(
            session_id=uuid4().hex,
            principal=dict(principal),
            created_at=now,
            expires_at=now + timedelta(seconds=max(1, ttl_seconds)),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired:
                del self._sessions[session_id]
                return None
            return session

    def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        now = datetime.now(UTC)
        with self._lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if session.expires_at <= now
            ]
            for session_id in expired:
                del self._sessions[session_id]
            return len(expired)


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
