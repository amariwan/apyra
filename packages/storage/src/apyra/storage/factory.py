"""Factory for configured storage backends."""

from __future__ import annotations

from functools import lru_cache

from .base import StorageClient
from .exceptions import StorageConfigError
from .settings import StorageBackend, get_storage_settings


@lru_cache(maxsize=1)
def get_storage_client() -> StorageClient:
    """Return a singleton StorageClient for the configured backend."""

    settings = get_storage_settings()

    if settings.storage_backend == StorageBackend.S3:
        from .s3 import S3StorageClient

        return S3StorageClient(settings)

    if settings.storage_backend == StorageBackend.FILESYSTEM:
        from .filesystem import FilesystemStorageClient

        return FilesystemStorageClient(settings)

    raise StorageConfigError(f"unsupported storage backend: {settings.storage_backend}")
