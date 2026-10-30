from fastapi import FastAPI

from apyra.fastapi import create_app, set_operation_ids, simplify_operation_ids


def test_simplify_operation_ids() -> None:
    app = create_app()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    simplify_operation_ids(app)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/ping")
    assert getattr(route, "operation_id", None) == "ping"


def test_set_operation_ids_with_prefix() -> None:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    set_operation_ids(app, prefix="api_")
    route = next(route for route in app.routes if getattr(route, "path", None) == "/ping")
    assert getattr(route, "operation_id", None) == "api_ping"
