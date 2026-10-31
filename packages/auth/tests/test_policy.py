from datetime import UTC, datetime, timedelta, tzinfo
from typing import TypedDict

import pytest

from apyra.auth import (
    AllOfPolicy,
    AnyOfPolicy,
    AttributePolicy,
    AuthorizationError,
    InMemorySessionStore,
    PolicyEngine,
    RolePolicy,
    ScopePolicy,
    has_role,
)


class PrincipalWithRoles(TypedDict):
    sub: str
    roles: list[str]


def test_role_policy_matches_normalized_permissions_and_wildcards() -> None:
    policy = RolePolicy({"Admin": {"users:*"}, "reader": {"read"}})

    assert policy.allows({"roles": ["ADMIN"]}, "users:delete")
    assert policy.allows({"roles": ["reader"]}, "READ")
    assert not policy.allows({"roles": ["reader"]}, "write")
    assert not policy.allows({}, "read")


def test_role_hierarchy_uses_normalized_role_names() -> None:
    assert has_role(
        {"roles": ["ADMIN"]},
        "editor",
        hierarchy={"Admin": {"Editor"}},
    )


def test_scope_policy_uses_configured_claim_and_is_case_insensitive() -> None:
    policy = ScopePolicy(scope_claim="permissions")

    assert policy.allows({"permissions": ["Document:Read"]}, "document:read")
    assert policy.allows({"permissions": ["*"]}, "document:delete")
    assert not policy.allows({"scopes": ["document:read"]}, "document:read")


def test_policy_engine_denies_without_policies_and_raises_on_denial() -> None:
    engine = PolicyEngine()

    assert not engine.is_allowed({}, "read")
    with pytest.raises(AuthorizationError, match="not_authorized:read"):
        engine.authorize({}, "read")
    PolicyEngine(ScopePolicy()).authorize({"scopes": ["read"]}, "read")


def test_composite_policies_preserve_all_of_and_any_of_semantics() -> None:
    allow_read = ScopePolicy()
    allow_admin = RolePolicy({"admin": {"write"}})
    principal = {"scopes": ["read"], "roles": ["admin"]}

    assert AllOfPolicy(allow_read, allow_admin).allows(principal, "read") is False
    assert AnyOfPolicy(allow_read, allow_admin).allows(principal, "read")
    assert AllOfPolicy(allow_read, RolePolicy({})).allows(principal, "read") is False
    assert AnyOfPolicy(RolePolicy({}), ScopePolicy()).allows(principal, "read")


def test_empty_allow_policies_fail_closed_at_construction() -> None:
    with pytest.raises(ValueError, match="at least one policy"):
        AllOfPolicy()
    with pytest.raises(ValueError, match="at least one condition"):
        AttributePolicy({})


def test_attribute_policy_resolves_sources_and_callable_conditions() -> None:
    principal = {"tenant_id": "tenant-1"}
    resource = {"owner_id": "user-1"}

    def is_owner(value: object) -> bool:
        return value == "user-1"

    def is_not_deleted(value: object) -> bool:
        return value is None

    policy = AttributePolicy(
        {
            "principal.tenant_id": "tenant-1",
            "principal": principal,
            "resource.owner_id": is_owner,
            "context.approved": True,
        }
    )

    assert policy.allows(principal, "read", resource, {"approved": True})
    assert not policy.allows(principal, "read", resource, {"approved": False})
    assert not policy.allows({"tenant_id": "tenant-2"}, "read", resource, {"approved": True})

    def is_other_owner(value: object) -> bool:
        return value == "user-2"

    assert not AttributePolicy({"resource.owner_id": is_other_owner}).allows(
        principal, "read", resource
    )
    assert not AttributePolicy({"principal.missing": "required"}).allows(principal, "read")
    assert not AttributePolicy({"resource.deleted_at": None}).allows({}, "delete")
    assert not AttributePolicy({"resource.deleted_at": is_not_deleted}).allows({}, "delete")

    class Resource:
        owner_id = "user-1"
        deleted_at = None

    assert AttributePolicy({"resource.owner_id": "user-1"}).allows(principal, "read", Resource())
    assert AttributePolicy({"resource.deleted_at": None}).allows({}, "read", Resource())


def test_in_memory_session_store_expires_and_revokes_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [datetime(2026, 1, 1, tzinfo=UTC)]

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return clock[0]

    monkeypatch.setattr("apyra.auth.policy.datetime", FrozenDateTime)
    store = InMemorySessionStore()
    session = store.create({"sub": "user-1"}, ttl_seconds=3600, metadata={"source": "test"})

    assert store.get(session.session_id) == session
    assert session.principal == {"sub": "user-1"}
    assert session.metadata == {"source": "test"}
    clock[0] += timedelta(hours=1, seconds=1)
    assert store.get(session.session_id) is None
    assert store.cleanup_expired() == 0

    expired = store.create({"sub": "user-3"}, ttl_seconds=1)
    clock[0] += timedelta(seconds=2)
    store.create({"sub": "user-4"})
    assert store.cleanup_expired() == 0
    assert store.get(expired.session_id) is None

    expired = store.create({"sub": "user-5"})
    clock[0] += timedelta(hours=1, seconds=1)
    assert store.cleanup_expired() == 2
    assert store.get(expired.session_id) is None

    active = store.create({"sub": "user-2"})
    store.revoke(active.session_id)
    assert store.get(active.session_id) is None


@pytest.mark.parametrize("ttl_seconds", [0, -1, True, 1.5])
def test_in_memory_session_store_rejects_invalid_ttl(ttl_seconds: object) -> None:
    with pytest.raises(ValueError, match="ttl_seconds must be a positive integer"):
        InMemorySessionStore().create({}, ttl_seconds=ttl_seconds)  # type: ignore[arg-type]


def test_in_memory_session_store_returns_isolated_session_snapshots() -> None:
    store = InMemorySessionStore()
    principal: PrincipalWithRoles = {"sub": "user-1", "roles": ["reader"]}
    metadata = {"labels": ["original"]}
    created = store.create(principal, metadata=metadata)

    principal["roles"].append("admin")
    metadata["labels"].append("caller-change")
    created.principal["roles"].append("admin")
    created.metadata["labels"].append("returned-change")

    first_read = store.get(created.session_id)
    assert first_read is not None
    assert first_read.principal == {"sub": "user-1", "roles": ["reader"]}
    assert first_read.metadata == {"labels": ["original"]}

    first_read.principal["roles"].append("owner")
    second_read = store.get(created.session_id)
    assert second_read is not None
    assert second_read.principal == {"sub": "user-1", "roles": ["reader"]}
