"""Storage contracts and backends for Apyra."""

from __future__ import annotations

from .base import FileMetadata, StorageClient, normalize_storage_path
from .exceptions import StorageConfigError, StorageError, StorageFileNotFoundError
from .factory import get_storage_client
from .filesystem import FilesystemStorageClient
from .s3 import S3StorageClient
from .settings import StorageBackend, StorageSettings

__all__ = [
    "FileMetadata",
    "FilesystemStorageClient",
    "S3StorageClient",
    "StorageBackend",
    "StorageClient",
    "StorageConfigError",
    "StorageError",
    "StorageFileNotFoundError",
    "StorageSettings",
    "get_storage_client",
    "normalize_storage_path",
]
