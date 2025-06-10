from typing import Any

from fastapi import HTTPException


class CloudApiException(HTTPException):
    """Class that represents a Cloud API error"""

    def __init__(
        self,
        detail: str | dict[str, Any],
        status_code: int = 500,
    ) -> None:
        """Initialize the CloudAPI exception."""
        super().__init__(status_code=status_code, detail=detail)
