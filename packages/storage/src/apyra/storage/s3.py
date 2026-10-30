"""S3-compatible storage backend (AWS S3 / MinIO)."""

from __future__ import annotations

import logging
from typing import Any, cast

from .base import FileMetadata, StorageClient, normalize_storage_path
from .exceptions import StorageConfigError, StorageError, StorageFileNotFoundError
from .settings import StorageSettings

logger = logging.getLogger("apyra.storage")


class S3StorageClient(StorageClient):
    """Store files in an S3-compatible object store."""

    _client_error_cls: type[Exception]

    def __init__(self, settings: StorageSettings) -> None:
        bucket = settings.s3_bucket.strip()
        if not bucket:
            raise StorageConfigError("s3 bucket is required")

        try:
            import boto3  # pyright: ignore[reportMissingImports]
            from botocore.config import Config  # pyright: ignore[reportMissingImports]
            from botocore.exceptions import ClientError  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise StorageConfigError("boto3 is required for the S3 backend") from exc

        endpoint_url = settings.s3_endpoint or None
        if endpoint_url and not settings.s3_secure and endpoint_url.startswith("https://"):
            endpoint_url = endpoint_url.replace("https://", "http://", 1)

        access_key = (
            settings.s3_access_key_id.get_secret_value().strip()
            if settings.s3_access_key_id
            else None
        )
        secret_key = (
            settings.s3_secret_access_key.get_secret_value().strip()
            if settings.s3_secret_access_key
            else None
        )

        session = cast(Any, boto3).session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.s3_region or None,
        )

        addressing_style = settings.s3_addressing_style or "auto"
        if endpoint_url and addressing_style == "auto":
            addressing_style = "path"

        config = Config(signature_version="s3v4", s3={"addressing_style": addressing_style})

        self._client = session.client("s3", endpoint_url=endpoint_url, config=config)
        self._bucket = bucket
        self._prefix = settings.s3_prefix.strip("/")
        self._client_error_cls = ClientError

        logger.info("S3StorageClient initialised — bucket '%s'", self._bucket)

    def _object_key(self, path: str) -> str:
        if not self._prefix:
            return path
        return f"{self._prefix}/{path}"

    def _to_public_key(self, object_key: str) -> str:
        if not self._prefix:
            return object_key
        prefix_with_sep = f"{self._prefix}/"
        if object_key.startswith(prefix_with_sep):
            return object_key[len(prefix_with_sep) :]
        return object_key

    def _is_not_found(self, exc: Exception) -> bool:
        if not isinstance(exc, self._client_error_cls):
            return False
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        error_obj = response.get("Error") or {}
        if not isinstance(error_obj, dict):
            return False
        code = error_obj.get("Code")
        return str(code) in {"404", "NoSuchKey", "NotFound"}

    def upload_file(
        self,
        file_bytes: bytes,
        path: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> FileMetadata:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        put_kwargs: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": object_key,
            "Body": file_bytes,
            "ContentType": content_type,
        }
        if metadata:
            put_kwargs["Metadata"] = metadata

        try:
            self._client.put_object(**put_kwargs)
        except Exception as exc:
            raise StorageError(f"s3 upload failed: {exc}") from exc

        return FileMetadata(path=normalized, size_bytes=len(file_bytes), content_type=content_type)

    def download_file(self, path: str) -> bytes:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return cast(bytes, obj["Body"].read())
        except Exception as exc:
            if self._is_not_found(exc):
                raise StorageFileNotFoundError(f"File not found: '{normalized}'") from exc
            raise StorageError(f"s3 download failed: {exc}") from exc

    def file_exists(self, path: str) -> bool:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        try:
            self._client.head_object(Bucket=self._bucket, Key=object_key)
            return True
        except Exception as exc:
            if self._is_not_found(exc):
                return False
            raise StorageError(f"s3 exists check failed: {exc}") from exc

    def delete_file(self, path: str) -> None:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        try:
            self._client.delete_object(Bucket=self._bucket, Key=object_key)
        except Exception as exc:
            raise StorageError(f"s3 delete failed: {exc}") from exc

    def file_size(self, path: str) -> int:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        try:
            meta = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except Exception as exc:
            if self._is_not_found(exc):
                raise StorageFileNotFoundError(f"File not found: '{normalized}'") from exc
            raise StorageError(f"s3 metadata failed: {exc}") from exc

        return int(meta.get("ContentLength") or 0)

    def list_files(self, prefix: str = "") -> list[str]:
        if prefix:
            normalized_prefix = normalize_storage_path(prefix)
            object_prefix = self._object_key(normalized_prefix)
        elif self._prefix:
            object_prefix = self._prefix
        else:
            object_prefix = ""

        if object_prefix and not object_prefix.endswith("/"):
            object_prefix = f"{object_prefix}/"

        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=self._bucket, Prefix=object_prefix):
                for item in page.get("Contents", []):
                    object_key = str(item.get("Key") or "")
                    if not object_key:
                        continue
                    keys.append(self._to_public_key(object_key))
        except Exception as exc:
            raise StorageError(f"s3 list failed: {exc}") from exc

        return sorted(keys)

    def generate_presigned_url(self, path: str, *, expires_in: int = 3600) -> str:
        normalized = normalize_storage_path(path)
        object_key = self._object_key(normalized)

        try:
            url: str = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            raise StorageError(f"s3 presigned URL failed: {exc}") from exc

        return url
