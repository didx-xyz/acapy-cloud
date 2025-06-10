from typing import Any

from aries_cloudcontroller import (
    RevRegWalletUpdatedResult as RevRegWalletUpdatedResultAcaPy,
)
from pydantic import Field


class RevRegWalletUpdatedResult(RevRegWalletUpdatedResultAcaPy):
    # Just overriding description to remove reference to Indy
    rev_reg_delta: dict[str, Any] | None = Field(
        default=None, description="Revocation registry delta"
    )
