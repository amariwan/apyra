# apyra-storage

Storage contracts and filesystem/S3 backends for Apyra.

## Installation

```bash
uv add apyra-storage
```

## Quick usage

```python
from apyra.storage import get_storage_client

client = get_storage_client()
client.upload_file(b"hello", "docs/hello.txt")
data = client.download_file("docs/hello.txt")
```

## Key exports

- `StorageClient`, `FileMetadata`
- `FilesystemStorageClient`, `S3StorageClient`
- `StorageSettings`, `StorageBackend`, `get_storage_settings`
- `get_storage_client`
- `StorageError`, `StorageFileNotFoundError`, `StorageConfigError`

## License

MIT