"""Framework-level errors."""


class ApyraError(Exception):
    """Base class for errors raised by Apyra."""


class ConfigurationError(ApyraError):
    """Raised when required configuration is missing or invalid."""
