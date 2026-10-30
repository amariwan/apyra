"""Observability primitives for Apyra."""

from __future__ import annotations

from .logging import configure_logging, get_request_id, set_request_id

setup_logging = configure_logging

__all__ = ["configure_logging", "get_request_id", "set_request_id"]
