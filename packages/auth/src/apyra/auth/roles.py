"""Role helpers."""

from __future__ import annotations


def extract_roles(payload: dict[str, object], claim: str = "roles") -> set[str]:
    value = payload.get(claim)
    if isinstance(value, str):
        return {item.strip().lower() for item in value.split(",") if item.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return set()


def has_role(
    payload: dict[str, object], role: str, *, hierarchy: dict[str, set[str]] | None = None
) -> bool:
    roles = extract_roles(payload)
    if role.lower() in roles:
        return True
    if hierarchy:
        for granted in list(roles):
            if role.lower() in hierarchy.get(granted, set()):
                return True
    return False


def extract_scopes(payload: dict[str, object], claim: str = "scopes") -> set[str]:
    value = payload.get(claim)
    if value is None:
        value = payload.get("scope")
    if isinstance(value, str):
        return {item.strip() for item in value.replace(",", " ").split() if item.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()
