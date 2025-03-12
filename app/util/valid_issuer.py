from logging import Logger
from typing import Tuple

from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.models.issuer import CredentialType
from app.services.acapy_wallet import assert_public_did
from app.util.wallet_type_checks import (
    assert_wallet_type_for_credential,
    get_wallet_type,
)


async def assert_issuer_public_did(
    aries_controller: AcaPyClient, bound_logger: Logger
) -> str:
    try:
        public_did = await assert_public_did(aries_controller)
    except CloudApiException as e:
        bound_logger.warning("Asserting agent has public DID failed: {}", e)
        raise CloudApiException(
            "Wallet making this request has no public DID. Only issuers with a public DID can make this request.",
            403,
        ) from e
    return public_did


async def assert_public_did_and_wallet_type(
    aries_controller: AcaPyClient, credential_type: CredentialType, bound_logger: Logger
) -> Tuple[str, str]:
    public_did = await assert_issuer_public_did(aries_controller, bound_logger)
    wallet_type = await get_wallet_type(aries_controller, bound_logger)
    assert_wallet_type_for_credential(wallet_type, credential_type)
    return public_did, wallet_type
