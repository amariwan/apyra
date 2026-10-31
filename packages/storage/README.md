# apyra-storage

Storage contracts and filesystem/S3 backends for Apyra.

## Installation

```bash
uv add apyra-storage
uv add 'apyra-storage[s3]' # boto3 for S3-compatible storage
```

## Quick usage

```python
from apyra.storage import get_storage_client

client = get_storage_client()
client.upload_file(b"hello", "docs/hello.txt")
data = client.download_file("docs/hello.txt")
```

## S3 endpoint security

`s3_secure` defaults to `true` and requires a configured endpoint to use HTTPS. Set it to `false` only when connecting to an explicitly configured HTTP endpoint, such as a local development service. An endpoint URL that uses HTTPS remains HTTPS regardless of this setting.

`S3StorageClient.generate_presigned_url()` accepts a positive integer `expires_in` duration in seconds (default: 3600) and raises `ValueError` for zero, negative, boolean, or non-integer values.

## Key exports

- `StorageClient`, `FileMetadata`
- `FilesystemStorageClient`, `S3StorageClient`
- `StorageSettings`, `StorageBackend`, `get_storage_settings`
- `get_storage_client`
- `StorageError`, `StorageFileNotFoundError`, `StorageConfigError`

## License

MIT
