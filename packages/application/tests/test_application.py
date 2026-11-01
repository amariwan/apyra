from __future__ import annotations

from apyra.application import ApplicationError, UseCase


class _EchoUseCase:
    async def execute(self, request: str) -> str:
        return request.upper()


def test_use_case_protocol_is_structural() -> None:
    use_case: UseCase[str, str] = _EchoUseCase()
    assert use_case is not None


def test_application_error_is_apyra_error() -> None:
    from apyra.core import ApyraError

    assert issubclass(ApplicationError, ApyraError)
