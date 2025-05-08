from typing import Any, Dict, Optional

from aries_cloudcontroller import (
    RevRegWalletUpdatedResult as RevRegWalletUpdatedResultAcaPy,
)
from pydantic import Field


class RevRegWalletUpdatedResult(RevRegWalletUpdatedResultAcaPy):
    # Just overriding description to remove reference to Indy
    rev_reg_delta: Optional[Dict[str, Any]] = Field(
        default=None, description="Revocation registry delta"
    )
