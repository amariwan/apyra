import os
import tempfile

import pytest

from apyra.storage import (
    FileMetadata,
    FilesystemStorageClient,
    StorageBackend,
    StorageError,
    StorageFileNotFoundError,
    StorageSettings,
    get_storage_client,
    normalize_storage_path,
)


def test_normalize_storage_path_rejects_traversal() -> None:
    with pytest.raises(StorageError):
        normalize_storage_path("../secret")


def test_filesystem_round_trip() -> None:
    with tempfile.TemporaryDirectory() as root:
        settings = StorageSettings(filesystem_root=root, storage_backend=StorageBackend.FILESYSTEM)
        client = FilesystemStorageClient(settings)

        metadata = client.upload_file(b"hello", "nested/file.txt", content_type="text/plain")
        assert isinstance(metadata, FileMetadata)
        assert client.file_exists("nested/file.txt")
        assert client.download_file("nested/file.txt") == b"hello"
        assert client.file_size("nested/file.txt") == 5
        assert client.list_files() == ["nested/file.txt"]

        client.delete_file("nested/file.txt")
        assert not client.file_exists("nested/file.txt")
        with pytest.raises(StorageFileNotFoundError):
            client.download_file("nested/file.txt")


def test_factory_filesystem(tmp_path) -> None:
    os.environ["FILESYSTEM_ROOT"] = str(tmp_path)
    get_storage_client.cache_clear()
    try:
        client = get_storage_client()
        assert client.file_exists("missing") is False
    finally:
        get_storage_client.cache_clear()
        os.environ.pop("FILESYSTEM_ROOT", None)


def test_filesystem_rejects_symlink_escape(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (root / "link.txt").symlink_to(outside)

    from apyra.storage import FilesystemStorageClient, StorageBackend, StorageError, StorageSettings

    client = FilesystemStorageClient(
        StorageSettings(filesystem_root=str(root), storage_backend=StorageBackend.FILESYSTEM)
    )
    with pytest.raises(StorageError):
        client.download_file("link.txt")
