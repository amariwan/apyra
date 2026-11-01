"""Application-layer errors."""

from __future__ import annotations

from apyra.core import ApyraError


class ApplicationError(ApyraError):
    """Base error for application/use-case failures."""
