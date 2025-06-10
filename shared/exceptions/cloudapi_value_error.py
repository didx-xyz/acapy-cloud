from typing import Any

from fastapi import HTTPException


class CloudApiValueError(HTTPException):
    """Class that represents a validation / value error"""

    def __init__(self, detail: str | dict[str, Any]) -> None:
        super().__init__(status_code=422, detail=detail)
