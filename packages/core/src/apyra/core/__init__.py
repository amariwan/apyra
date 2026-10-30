"""Core contracts and primitives for Apyra."""

from __future__ import annotations

from .errors import ApyraError, ConfigurationError
from .settings import Settings

__version__ = "0.1.0"

__all__ = ["ApyraError", "ConfigurationError", "Settings", "__version__"]
