"""Role helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast


def _items(value: object) -> Iterable[object] | None:
    if isinstance(value, (list, tuple, set)):
        return cast(Iterable[object], value)
    return None


def extract_roles(payload: dict[str, object], claim: str = "roles") -> set[str]:
    """Normalize role names from a string or iterable claim into a set."""
    value = payload.get(claim)
    if isinstance(value, str):
        return {item.strip().lower() for item in value.split(",") if item.strip()}
    items = _items(value)
    if items is not None:
        return {str(item).strip().lower() for item in items if str(item).strip()}
    return set()


def has_role(
    payload: dict[str, object], role: str, *, hierarchy: dict[str, set[str]] | None = None
) -> bool:
    """Check for a role directly or through one level of configured hierarchy."""
    roles = extract_roles(payload)
    if role.lower() in roles:
        return True
    if hierarchy:
        normalized_hierarchy = {
            str(granted).strip().lower(): {
                str(inherited).strip().lower() for inherited in inherited_roles
            }
            for granted, inherited_roles in hierarchy.items()
        }
        for granted in list(roles):
            if role.lower() in normalized_hierarchy.get(granted, set()):
                return True
    return False


def extract_scopes(payload: dict[str, object], claim: str = "scopes") -> set[str]:
    """Normalize scopes from the configured claim or the standard ``scope`` claim."""
    value = payload.get(claim)
    if value is None:
        value = payload.get("scope")
    if isinstance(value, str):
        return {item.strip() for item in value.replace(",", " ").split() if item.strip()}
    items = _items(value)
    if items is not None:
        return {str(item).strip() for item in items if str(item).strip()}
    return set()
