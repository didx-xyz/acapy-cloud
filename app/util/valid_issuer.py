from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.services.acapy_wallet import assert_public_did
from shared.log_config import Logger


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
