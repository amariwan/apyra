"""Filesystem-storage-backed Apyra FastAPI application.

Demonstrates upload/download/delete via the storage contract.

Run with::

    uv run uvicorn main:app --app-dir examples/storage-api --reload
"""

from __future__ import annotations

from typing import Annotated

from apyra.core import Settings
from apyra.fastapi import create_app
from apyra.storage import StorageClient, get_storage_client
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, UploadFile

api = APIRouter()


def get_storage() -> StorageClient:
    return get_storage_client()


class UploadResult(BaseModel):
    path: str
    size_bytes: int
    content_type: str


@api.post("/files/{path:path}", response_model=UploadResult)
async def upload(
    path: str, file: UploadFile, storage: Annotated[StorageClient, Depends(get_storage)]
) -> UploadResult:
    data = await file.read()
    meta = storage.upload_file(
        data, path, content_type=file.content_type or "application/octet-stream"
    )
    return UploadResult(path=meta.path, size_bytes=meta.size_bytes, content_type=meta.content_type)


@api.get("/files/{path:path}")
async def download(path: str, storage: Annotated[StorageClient, Depends(get_storage)]) -> dict:
    try:
        data = storage.download_file(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"path": path, "size_bytes": len(data)}


@api.delete("/files/{path:path}", status_code=204)
async def delete(path: str, storage: Annotated[StorageClient, Depends(get_storage)]) -> None:
    storage.delete_file(path)


app = create_app(
    title="Storage Apyra API",
    routers=[api],
    settings=Settings(api_prefix="/api"),
)
