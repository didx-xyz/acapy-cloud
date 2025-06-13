from sqlalchemy import TypeDecorator
from sqlalchemy.sql.sqltypes import String


class StringList(TypeDecorator):  # pylint: disable=W0223
    impl = String

    cache_ok = False  # Resolves warning: https://sqlalche.me/e/20/cprf

    def process_bind_param(self, value: list[str] | None, _) -> str | None:  # noqa: ANN001
        if isinstance(value, list):
            return ",".join(value)

        return value

    def process_result_value(self, value: str, _) -> list[str] | None:  # noqa: ANN001
        return value.split(",") if value is not None else None
