"""Storage-specific exceptions."""


class StorageError(Exception):
    """Base exception for all storage operations."""


class StorageFileNotFoundError(StorageError):
    """Raised when a requested file does not exist in storage."""


class StorageConfigError(StorageError):
    """Raised when storage configuration is invalid or incomplete."""
