# apyra-storage

Storage contracts and filesystem/S3 backends for Apyra.

## Purpose

`apyra-storage` defines a storage client contract plus filesystem and S3 backends, with path normalization and typed errors. Backends are selected via settings/extras.

## Installation

```bash
uv add apyra-storage               # filesystem backend
uv add "apyra-storage[s3]"         # + S3 (boto3)
```

## Minimal usage

```python
from apyra.storage import get_storage_client

client = get_storage_client()  # configured via StorageSettings
```

## Optional dependencies

- `s3`: `boto3`, `botocore`

## Configuration

`StorageSettings` / `StorageBackend` via Pydantic Settings. Environment prefix defined in `apyra.storage.settings`.

## Public API

- `StorageClient`, `FileMetadata`
- `FilesystemStorageClient`, `S3StorageClient`
- `StorageBackend`, `StorageSettings`, `get_storage_client`
- `StorageError`, `StorageFileNotFoundError`, `StorageConfigError`
- `normalize_storage_path`

## Error behavior

Missing files raise `StorageFileNotFoundError`; configuration problems raise `StorageConfigError`; other failures raise `StorageError`.

## Integration

Used by application code for uploads/downloads. Combine with `apyra-fastapi` for HTTP upload endpoints.

## Compatibility

- Python ≥ 3.12
- S3 extra requires boto3 ≥ 1.34

## License

MIT
