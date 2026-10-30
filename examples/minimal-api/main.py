"""Minimal Apyra FastAPI application."""

from apyra.core import Settings
from apyra.fastapi import create_app

from fastapi import APIRouter

router = APIRouter()


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from Apyra"}


app = create_app(
    title="Minimal Apyra API",
    routers=[router],
    settings=Settings(api_prefix="/api"),
)
