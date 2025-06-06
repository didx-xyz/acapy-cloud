from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.services import acapy_wallet
from shared.log_config import get_logger

logger = get_logger(__name__)


async def assert_public_did(aries_controller: AcaPyClient) -> str:
    """Assert tenant has a public DID and return it."""
    try:
        logger.debug("Asserting client has public DID")
        public_did = await acapy_wallet.assert_public_did(aries_controller)
    except CloudApiException as e:
        log_message = f"Asserting public DID failed: {e}"

        if e.status_code == 403:
            logger.info(log_message)
            client_error_message = (
                "Wallet making this request has no public DID. "
                "Only issuers with a public DID can make this request."
            )
        else:
            logger.error(log_message)
            client_error_message = (
                "Something went wrong while asserting if request is from a valid "
                "issuer. Please try again."
            )

        raise CloudApiException(client_error_message, e.status_code) from e
    return public_did
