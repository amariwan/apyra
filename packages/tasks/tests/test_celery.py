import pytest

from apyra.tasks import CeleryAdapter, CeleryUnavailableError


class FakeCeleryApp:
    def __init__(self) -> None:
        self.registered: list[tuple[object, dict[str, object]]] = []

    def task(self, **options):
        def decorator(func):
            self.registered.append((func, options))
            return func

        return decorator


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
        adapter.task(lambda value: value)
