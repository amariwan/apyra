import builtins
from collections.abc import Callable
from typing import Any

import pytest

from apyra.tasks import CeleryAdapter, CeleryUnavailableError


class FakeCeleryApp:
    def __init__(self) -> None:
        self.registered: list[tuple[object, dict[str, object]]] = []

    def task(self, **options: object) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.registered.append((func, options))
            return func

        return decorator


def increment(value: int) -> int:
    return value + 1


def test_celery_adapter_registers_task() -> None:
    app = FakeCeleryApp()
    adapter = CeleryAdapter(app=app, default_retries=3, default_timeout=5)

    @adapter.task
    def work(value: int) -> int:
        return value + 1

    assert app.registered[0][1] == {
        "max_retries": 3,
        "autoretry_for": (Exception,),
        "soft_time_limit": 5,
        "time_limit": 5,
    }


def test_celery_adapter_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "celery", None)
    adapter = CeleryAdapter()
    with pytest.raises(CeleryUnavailableError):
        adapter.task(increment)


def test_celery_adapter_does_not_mask_internal_import_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def broken_celery(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "celery":
            raise ImportError("celery has a broken internal dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_celery)
    with pytest.raises(ImportError, match="broken internal dependency"):
        CeleryAdapter().task(increment)
