"""FastAPI integration for Apyra."""

from __future__ import annotations

from .app import create_app
from .auth import get_current_token, get_current_user, require_roles, require_scopes
from .cbv import cbv, delete, get, patch, post, put
from .csrf import require_csrf
from .openapi import set_operation_ids, simplify_operation_ids
from .timing import TimingMiddleware, register_timing_middleware

__all__ = [
    "TimingMiddleware",
    "cbv",
    "create_app",
    "delete",
    "get",
    "get_current_token",
    "get_current_user",
    "patch",
    "post",
    "put",
    "register_timing_middleware",
    "require_csrf",
    "require_roles",
    "require_scopes",
    "set_operation_ids",
    "simplify_operation_ids",
]
