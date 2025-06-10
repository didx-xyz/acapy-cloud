from fastapi.exceptions import HTTPException


class TrustRegistryException(HTTPException):
    """Class that represents a trust registry error"""

    def __init__(
        self,
        detail: str,
        status_code: int = 403,
    ) -> None:
        """Initialize the trust registry exception."""
        super().__init__(status_code=status_code, detail=detail)
