"""OpenAPI utilities for Apyra FastAPI applications."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute


def simplify_operation_ids(app: FastAPI) -> None:
    """Use route function names as OpenAPI operation IDs."""

    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


def set_operation_ids(app: FastAPI, *, prefix: str = "") -> None:
    """Assign deterministic operation IDs to all API routes."""

    for route in app.routes:
        if isinstance(route, APIRoute) and route.operation_id is None:
            name = route.name
            route.operation_id = f"{prefix}{name}" if prefix else name
