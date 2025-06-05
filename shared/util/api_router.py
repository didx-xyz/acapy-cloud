from typing import Any, Callable

from fastapi import APIRouter as FastAPIRouter
from fastapi.types import DecoratedCallable


# Purpose of custom APIRouter is to prevent manually having to add
# duplicate route decorators with / without a trailing slash,
# in order to support routes without redirecting.
#
# See discussion at: https://github.com/tiangolo/fastapi/issues/2060#issuecomment-834868906
class APIRouter(FastAPIRouter):
    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        add_path = super().api_route(
            path, include_in_schema=include_in_schema, **kwargs
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path,
            include_in_schema=False,  # Will not be included in generated schema
            **kwargs,
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator
