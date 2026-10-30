"""Storage abstraction: interface, metadata, and path helpers."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from pathlib import PurePosixPath

from .exceptions import StorageError


@dataclasses.dataclass(frozen=True, slots=True)
class FileMetadata:
    """Metadata returned after a successful upload."""

    path: str
    size_bytes: int
    content_type: str


def normalize_storage_path(path: str) -> str:
    """Normalize and validate a storage path.

    Returns a cleaned POSIX path string. Rejects empty, absolute, and
    directory-traversal paths.
    """

    stripped = path.strip()
    if not stripped:
        raise StorageError("storage path must not be empty")

    normalized = str(PurePosixPath(stripped))
    if not normalized or normalized in {".", "/"}:
        raise StorageError("storage path must not be empty")

    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts:
        raise StorageError("storage path is invalid")

    return normalized


class StorageClient(ABC):
    """Backend-agnostic byte-storage interface."""

    @abstractmethod
    def upload_file(
        self,
        file_bytes: bytes,
        path: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> FileMetadata:
        """Store file bytes at path and return metadata."""

    @abstractmethod
    def download_file(self, path: str) -> bytes:
        """Load bytes by path."""

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Return whether a file at path exists."""

    @abstractmethod
    def delete_file(self, path: str) -> None:
        """Delete the file at path. No-op if already absent."""

    @abstractmethod
    def file_size(self, path: str) -> int:
        """Return file size in bytes."""

    @abstractmethod
    def list_files(self, prefix: str = "") -> list[str]:
        """List file paths under prefix."""

    @abstractmethod
    def generate_presigned_url(self, path: str, *, expires_in: int = 3600) -> str:
        """Return a time-limited download URL for path."""
