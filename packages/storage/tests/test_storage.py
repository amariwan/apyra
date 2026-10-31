import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from apyra.storage import (
    FileMetadata,
    FilesystemStorageClient,
    StorageBackend,
    StorageConfigError,
    StorageError,
    StorageFileNotFoundError,
    StorageSettings,
    get_storage_client,
    normalize_storage_path,
)
from apyra.storage import factory as storage_factory
from apyra.storage import s3 as storage_s3


def test_normalize_storage_path_rejects_traversal() -> None:
    with pytest.raises(StorageError):
        normalize_storage_path("../secret")


@pytest.mark.parametrize(
    "path",
    [
        r"..\secret",
        r"folder\..\secret",
        r".. \secret",
        r".. .\secret",
        r"C:\secret",
        r"C:secret",
        r"\secret",
    ],
)
def test_normalize_storage_path_rejects_windows_traversal_and_roots(path: str) -> None:
    with pytest.raises(StorageError, match="invalid"):
        normalize_storage_path(path)


def test_storage_settings_repr_redacts_endpoint_credentials_without_changing_value() -> None:
    endpoint = "https://user:storage-secret@minio.example:9000"
    settings = StorageSettings(s3_endpoint=endpoint)

    assert "storage-secret" not in repr(settings)
    assert settings.s3_endpoint == endpoint


def test_normalize_storage_path_rejects_null_bytes() -> None:
    with pytest.raises(StorageError, match="invalid"):
        normalize_storage_path("nested/bad\x00name.txt")


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


def test_factory_filesystem(tmp_path: Path) -> None:
    os.environ["FILESYSTEM_ROOT"] = str(tmp_path)
    get_storage_client.cache_clear()
    try:
        client = get_storage_client()
        assert client.file_exists("missing") is False
    finally:
        get_storage_client.cache_clear()
        os.environ.pop("FILESYSTEM_ROOT", None)


def test_factory_s3_uses_configured_settings_and_caches_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = StorageSettings(storage_backend=StorageBackend.S3)
    sentinel = object()
    received_settings: list[StorageSettings] = []

    def build_s3(received: StorageSettings) -> object:
        received_settings.append(received)
        return sentinel

    monkeypatch.setattr(storage_factory, "get_storage_settings", lambda: settings)
    monkeypatch.setattr(storage_s3, "S3StorageClient", build_s3)
    get_storage_client.cache_clear()
    try:
        client = get_storage_client()
        assert get_storage_client() is client
        assert client is sentinel
        assert received_settings == [settings]
    finally:
        get_storage_client.cache_clear()


def test_filesystem_rejects_symlink_escape(tmp_path: Path) -> None:
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


def test_filesystem_upload_maps_parent_directory_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FilesystemStorageClient(
        StorageSettings(filesystem_root=str(tmp_path), storage_backend=StorageBackend.FILESYSTEM)
    )
    original_mkdir = cast(Callable[..., None], Path.mkdir)
    failing_directory = tmp_path / "blocked"

    def mkdir(path: Path, *args: object, **kwargs: object) -> None:
        if path == failing_directory:
            raise PermissionError("permission denied")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "mkdir", mkdir)

    with pytest.raises(StorageError, match="could not write file"):
        client.upload_file(b"data", "blocked/file.txt")


def test_filesystem_file_size_maps_stat_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FilesystemStorageClient(
        StorageSettings(filesystem_root=str(tmp_path), storage_backend=StorageBackend.FILESYSTEM)
    )

    class BrokenPath:
        def exists(self) -> bool:
            return True

        def stat(self) -> os.stat_result:
            raise PermissionError("permission denied")

    def resolve_broken_path(_path: str) -> Path:
        return cast(Path, BrokenPath())

    monkeypatch.setattr(client, "_resolve_path", resolve_broken_path)

    with pytest.raises(StorageError, match="could not read file size"):
        client.file_size("file.txt")


def test_filesystem_missing_operations_are_consistent(tmp_path: Path) -> None:
    client = FilesystemStorageClient(
        StorageSettings(filesystem_root=str(tmp_path), storage_backend=StorageBackend.FILESYSTEM)
    )

    assert client.file_exists("missing.txt") is False
    assert client.list_files("missing-prefix") == []
    client.delete_file("missing.txt")
    with pytest.raises(StorageFileNotFoundError):
        client.file_size("missing.txt")
    with pytest.raises(StorageError, match="presigned URLs are not supported"):
        client.generate_presigned_url("missing.txt")


def test_filesystem_maps_read_and_delete_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FilesystemStorageClient(
        StorageSettings(filesystem_root=str(tmp_path), storage_backend=StorageBackend.FILESYSTEM)
    )
    (tmp_path / "file.txt").write_bytes(b"data")

    def fail_read(_path: Path) -> bytes:
        raise PermissionError("permission denied")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", fail_read)
        with pytest.raises(StorageError, match="could not read file"):
            client.download_file("file.txt")

    def fail_unlink(_path: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(StorageError, match="could not delete file"):
        client.delete_file("file.txt")


def test_filesystem_rejects_empty_or_unwritable_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(StorageConfigError, match="root must not be empty"):
        FilesystemStorageClient(
            StorageSettings(filesystem_root="", storage_backend=StorageBackend.FILESYSTEM)
        )

    def deny_access(_path: str | bytes | os.PathLike[str], _mode: int) -> bool:
        return False

    monkeypatch.setattr(os, "access", deny_access)
    with pytest.raises(StorageConfigError, match="not writable"):
        FilesystemStorageClient(
            StorageSettings(
                filesystem_root=str(tmp_path), storage_backend=StorageBackend.FILESYSTEM
            )
        )


def test_filesystem_maps_root_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_mkdir(_path: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    with pytest.raises(StorageConfigError, match="could not create filesystem root"):
        FilesystemStorageClient(
            StorageSettings(
                filesystem_root=str(tmp_path / "storage"),
                storage_backend=StorageBackend.FILESYSTEM,
            )
        )
