from typing import Optional

from aries_cloudcontroller import DID, AcaPyClient, DIDCreate
from pydantic import BaseModel

from app.exceptions.cloud_api_error import CloudApiException
from shared.log_config import get_logger

logger = get_logger(__name__)


class Did(BaseModel):
    did: str
    verkey: str


async def assert_public_did(aries_controller: AcaPyClient) -> str:
    """assert the agent has a public did, throwing an error otherwise.

    Args:
        aries_controller (AcaPyClient): the aca-py client.

    Returns:
        str: the public did formatted as fully qualified did
    """
    # Assert the agent has a public did
    logger.info("Fetching public DID")
    public_did = await aries_controller.wallet.get_public_did()

    if not public_did.result or not public_did.result.did:
        raise CloudApiException("Agent has no public did.", 403)

    logger.info("Successfully fetched public DID.")
    return f"did:sov:{public_did.result.did}"


async def create_did(
    controller: AcaPyClient, did_create: Optional[DIDCreate] = None
) -> Did:
    """Create a local did

    Args:
        controller (AcaPyClient): [description]

    Raises:
        HTTPException: If the creation of the did failed

    Returns:
        Did: The created did
    """
    logger.info("Creating local DID")
    if did_create is None:
        did_create = DIDCreate()
    did_result = await controller.wallet.create_did(body=did_create)

    if (
        not did_result.result
        or not did_result.result.did
        or not did_result.result.verkey
    ):
        logger.error("Failed to create DID: `{}`.", did_result)
        raise CloudApiException("Error creating did.")

    logger.info("Successfully created local DID.")
    return Did(did=did_result.result.did, verkey=did_result.result.verkey)


async def set_public_did(
    controller: AcaPyClient,
    did: str,
    connection_id: str = None,
    create_transaction_for_endorser: bool = False,
) -> DID:
    """Set the public did.

    Args:
        controller (AcaPyClient): aca-py client
        did (str): the did to set as public

    Raises:
        CloudApiException: if registration of the public did failed

    Returns:
        DID: the did
    """
    logger.info("Setting public DID")
    result = await controller.wallet.set_public_did(
        did=did,
        conn_id=connection_id,
        create_transaction_for_endorser=create_transaction_for_endorser,
    )

    if not result.result and not create_transaction_for_endorser:
        raise CloudApiException(f"Error setting public did to `{did}`.", 400)

    logger.info("Successfully set public DID.")
    return result.to_dict()


async def get_public_did(controller: AcaPyClient) -> Did:
    """Get the public did.

    Args:
        controller (AcaPyClient): aca-py client

    Raises:
        CloudApiException: if retrieving the public did failed.

    Returns:
        Did: the public did
    """
    logger.info("Fetching public DID")
    result = await controller.wallet.get_public_did()

    if not result.result:
        raise CloudApiException("No public did found", 404)

    logger.info("Successfully fetched public DID.")
    return Did(did=result.result.did, verkey=result.result.verkey)
