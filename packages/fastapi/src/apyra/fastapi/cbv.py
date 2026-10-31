"""Class-based view helpers for FastAPI routers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, cast

from fastapi import APIRouter


def _route_decorator(
    method: str, path: str, **kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__cbv_route__ = (method.upper(), path, kwargs)  # type: ignore[attr-defined]
        return func

    return decorator


def get(path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a class method as a GET route for a ``@cbv`` router."""
    return _route_decorator("GET", path, **kwargs)


def post(path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a class method as a POST route for a ``@cbv`` router."""
    return _route_decorator("POST", path, **kwargs)


def put(path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a class method as a PUT route for a ``@cbv`` router."""
    return _route_decorator("PUT", path, **kwargs)


def delete(path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a class method as a DELETE route for a ``@cbv`` router."""
    return _route_decorator("DELETE", path, **kwargs)


def patch(path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a class method as a PATCH route for a ``@cbv`` router."""
    return _route_decorator("PATCH", path, **kwargs)


def cbv(router: APIRouter) -> Callable[[type[Any]], type[Any]]:
    """Register class methods decorated with route decorators on *router*."""

    def decorator(cls: type[Any]) -> type[Any]:
        for name, method in list(cls.__dict__.items()):
            route = cast(
                tuple[str, str, dict[str, Any]] | None,
                getattr(method, "__cbv_route__", None),
            )
            if not isinstance(route, tuple) or len(route) != 3:
                continue
            http_method, path, kwargs = route

            original_signature = inspect.signature(method)
            parameters = list(original_signature.parameters.values())
            if not parameters or parameters[0].name != "self":
                raise TypeError(f"{cls.__name__}.{name} must declare self as its first parameter")
            route_parameters = parameters[1:]
            endpoint_signature = original_signature.replace(parameters=route_parameters)

            async def endpoint(
                *args: Any, method: Callable[..., Any] = method, **kwargs: Any
            ) -> Any:
                instance = cls()
                result = method(instance, *args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

            endpoint.__name__ = name
            endpoint.__doc__ = method.__doc__
            endpoint.__signature__ = endpoint_signature  # type: ignore[attr-defined]
            endpoint.__annotations__ = {
                parameter.name: parameter.annotation
                for parameter in route_parameters
                if parameter.annotation is not inspect.Parameter.empty
            }
            if original_signature.return_annotation is not inspect.Signature.empty:
                endpoint.__annotations__["return"] = original_signature.return_annotation

            router.add_api_route(path, endpoint, methods=[http_method], **kwargs)

        return cls

    return decorator
