"""Filesystem storage backend for local development and testing."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import FileMetadata, StorageClient, normalize_storage_path
from .exceptions import StorageConfigError, StorageError, StorageFileNotFoundError
from .settings import StorageSettings

logger: logging.Logger = logging.getLogger("apyra.storage")


class FilesystemStorageClient(StorageClient):
    """Store files on the local filesystem."""

    def __init__(self, settings: StorageSettings) -> None:
        root = settings.filesystem_root.strip()
        if not root:
            raise StorageConfigError("filesystem root must not be empty")

        self._root = Path(root)

        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as err:
            raise StorageConfigError(f"could not create filesystem root: {err}") from err

        if not os.access(self._root, os.W_OK):
            raise StorageConfigError(f"filesystem root is not writable: {self._root}")

        logger.info("FilesystemStorageClient initialised — root '%s'", self._root)

    def _resolve_path(self, path: str) -> Path:
        normalized = normalize_storage_path(path)
        root = self._root.resolve()
        # Reject symlinked path components before resolving the final target.
        current = root
        for part in Path(normalized).parts:
            current = current / part
            if current.is_symlink():
                raise StorageError("symbolic links are not allowed in storage paths")
        target = (root / normalized).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise StorageError("storage path escapes configured root") from exc
        if target.is_symlink():
            raise StorageError("symbolic links are not allowed in storage paths")
        return target

    def upload_file(
        self,
        file_bytes: bytes,
        path: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> FileMetadata:
        """Write bytes below the configured root and return their metadata."""
        file_path = self._resolve_path(path)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(file_bytes)
        except OSError as err:
            raise StorageError(f"could not write file: {err}") from err

        return FileMetadata(
            path=normalize_storage_path(path), size_bytes=len(file_bytes), content_type=content_type
        )

    def download_file(self, path: str) -> bytes:
        """Read a stored file, raising ``StorageFileNotFoundError`` when absent."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise StorageFileNotFoundError(f"File not found: '{normalize_storage_path(path)}'")

        try:
            return file_path.read_bytes()
        except (OSError, PermissionError) as err:
            raise StorageError(f"could not read file: {err}") from err

    def file_exists(self, path: str) -> bool:
        """Return whether the normalized path names a regular stored file."""
        file_path = self._resolve_path(path)
        return file_path.exists() and file_path.is_file() and not file_path.is_symlink()

    def delete_file(self, path: str) -> None:
        """Delete a stored file; deleting an absent path is a no-op."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return

        try:
            file_path.unlink()
        except (OSError, PermissionError) as err:
            raise StorageError(f"could not delete file: {err}") from err

    def file_size(self, path: str) -> int:
        """Return the file size in bytes, raising when the path is absent."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise StorageFileNotFoundError(f"File not found: '{normalize_storage_path(path)}'")

        try:
            return file_path.stat().st_size
        except OSError as err:
            raise StorageError(f"could not read file size: {err}") from err

    def list_files(self, prefix: str = "") -> list[str]:
        """List sorted file keys below the optional root-relative path prefix."""
        if prefix:
            search_root = self._resolve_path(prefix)
        else:
            search_root = self._root.resolve()

        if not search_root.exists():
            return []

        keys: list[str] = []
        for file_path in search_root.rglob("*"):
            if file_path.is_file() and not file_path.is_symlink():
                relative = file_path.relative_to(self._root.resolve())
                keys.append(str(relative))

        return sorted(keys)

    def generate_presigned_url(self, path: str, *, expires_in: int = 3600) -> str:
        """Raise ``StorageError`` because local files have no presigned URL support."""
        raise StorageError("presigned URLs are not supported by the filesystem backend")
