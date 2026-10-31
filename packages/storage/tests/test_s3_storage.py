from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from apyra.storage import (
    S3StorageClient,
    StorageConfigError,
    StorageError,
    StorageFileNotFoundError,
    StorageSettings,
)


class FakeS3:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.pages = [
            {"Contents": [{"Key": "uploads/z.txt"}, {"Key": ""}]},
            {"Contents": [{"Key": "uploads/a.txt"}, {"Key": "outside/b.txt"}]},
        ]
        self.fail: dict[str, Exception] = {}

    def _call(self, name: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, kwargs))
        if name in self.fail:
            raise self.fail[name]
        return {"ContentLength": 7}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("put_object", **kwargs)

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("get_object", **kwargs) | {"Body": FakeBody()}

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("head_object", **kwargs)

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("delete_object", **kwargs)

    def get_paginator(self, operation: str) -> FakePaginator:
        assert operation == "list_objects_v2"
        return FakePaginator(self)

    def generate_presigned_url(
        self, operation: str, *, Params: dict[str, str], ExpiresIn: int
    ) -> str:
        self._call(
            "generate_presigned_url", operation=operation, Params=Params, ExpiresIn=ExpiresIn
        )
        return "https://storage.example/signed"


class FakeBody:
    def read(self) -> bytes:
        return b"payload"


class FakePaginator:
    def __init__(self, client: FakeS3) -> None:
        self.client = client

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.client.calls.append(("paginate", kwargs))
        if "paginate" in self.client.fail:
            raise self.client.fail["paginate"]
        return self.client.pages


def make_client() -> tuple[S3StorageClient, FakeS3]:
    client = S3StorageClient.__new__(S3StorageClient)
    fake = FakeS3()
    client._client = fake
    client._bucket = "assets"
    client._prefix = "uploads"
    client._client_error_cls = ClientError
    return client, fake


def not_found() -> ClientError:
    return ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")


def test_s3_storage_operations_apply_prefix_and_map_metadata() -> None:
    client, fake = make_client()

    metadata = client.upload_file(
        b"payload", "folder/file.txt", content_type="text/plain", metadata={"owner": "user"}
    )
    assert metadata.path == "folder/file.txt"
    assert metadata.size_bytes == 7
    assert fake.calls[0] == (
        "put_object",
        {
            "Bucket": "assets",
            "Key": "uploads/folder/file.txt",
            "Body": b"payload",
            "ContentType": "text/plain",
            "Metadata": {"owner": "user"},
        },
    )
    assert client.download_file("folder/file.txt") == b"payload"
    assert client.file_exists("folder/file.txt")
    assert client.file_size("folder/file.txt") == 7
    client.delete_file("folder/file.txt")
    assert client.list_files() == ["a.txt", "z.txt"]
    assert client.list_files("folder") == []
    assert client.generate_presigned_url("folder/file.txt", expires_in=60).startswith("https://")


@pytest.mark.parametrize("expires_in", [0, -1, True, 1.5])
def test_s3_presigned_url_rejects_invalid_expiration(expires_in: int) -> None:
    client, fake = make_client()

    with pytest.raises(ValueError, match="expires_in must be a positive integer"):
        client.generate_presigned_url("file.txt", expires_in=expires_in)

    assert fake.calls == []


@pytest.mark.parametrize(
    ("method", "expected", "operation"),
    [
        ("download_file", StorageFileNotFoundError, "get_object"),
        ("file_exists", None, "head_object"),
        ("file_size", StorageFileNotFoundError, "head_object"),
    ],
)
def test_s3_storage_maps_missing_objects(
    method: str, expected: type[Exception] | None, operation: str
) -> None:
    client, fake = make_client()
    fake.fail[operation] = not_found()

    if expected is None:
        assert getattr(client, method)("missing.txt") is False
    else:
        with pytest.raises(expected):
            getattr(client, method)("missing.txt")


@pytest.mark.parametrize(
    ("method", "operation"),
    [
        ("upload_file", "put_object"),
        ("download_file", "get_object"),
        ("file_exists", "head_object"),
        ("delete_file", "delete_object"),
        ("file_size", "head_object"),
        ("list_files", "paginate"),
        ("generate_presigned_url", "generate_presigned_url"),
    ],
)
def test_s3_storage_wraps_service_failures(method: str, operation: str) -> None:
    client, fake = make_client()
    fake.fail[operation] = RuntimeError("service unavailable")

    with pytest.raises(StorageError):
        if method == "upload_file":
            client.upload_file(b"data", "file.txt")
        elif method == "list_files":
            client.list_files()
        elif method == "generate_presigned_url":
            client.generate_presigned_url("file.txt")
        else:
            getattr(client, method)("file.txt")


def test_s3_storage_rejects_path_traversal_and_plaintext_secure_endpoint() -> None:
    client, _ = make_client()
    with pytest.raises(StorageError):
        client.download_file("../secret")

    with pytest.raises(StorageConfigError, match="must use HTTPS"):
        S3StorageClient(
            StorageSettings(s3_bucket="assets", s3_endpoint="http://minio:9000", s3_secure=True)
        )


def test_s3_insecure_mode_preserves_explicit_https_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import boto3.session

    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def client(self, service: str, *, endpoint_url: str, config: object) -> object:
            captured["service"] = service
            captured["endpoint_url"] = endpoint_url
            return object()

    monkeypatch.setattr(boto3.session, "Session", FakeSession)

    S3StorageClient(
        StorageSettings(
            s3_bucket="assets",
            s3_endpoint="https://minio.example:9000",
            s3_secure=False,
        )
    )

    assert captured["service"] == "s3"
    assert captured["endpoint_url"] == "https://minio.example:9000"
