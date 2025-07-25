from aries_cloudcontroller import DID, AcaPyClient, CreateCheqdDIDRequest

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.wallet import DIDCreate
from shared.log_config import get_logger

logger = get_logger(__name__)


async def assert_public_did(aries_controller: AcaPyClient) -> str:
    """Assert the agent has a public did, throwing an error otherwise.

    Args:
        aries_controller (AcaPyClient): the aca-py client.

    Returns:
        str: the public did formatted as fully qualified did

    """
    # Assert the agent has a public did
    logger.debug("Fetching public DID")
    public_did = await handle_acapy_call(
        logger=logger, acapy_call=aries_controller.wallet.get_public_did
    )

    if not public_did.result or not public_did.result.did:
        raise CloudApiException("Agent has no public did.", 403)

    logger.debug("Successfully fetched public DID.")

    return public_did.result.did


async def create_did(
    controller: AcaPyClient, did_create: DIDCreate | None = None
) -> DID:
    """Create a local did

    Args:
        controller (AcaPyClient): The acapy client.
        did_create (DIDCreate): The did create object.

    Raises:
        HTTPException: If the creation of the did failed

    Returns:
        DID: The created did

    """
    logger.debug("Creating local DID")

    if did_create is None:
        did_create = DIDCreate()

    did_method = did_create.method

    if did_method == "cheqd":
        create_cheqd_did_options = did_create.to_acapy_options().to_dict()
        if did_create.seed:
            create_cheqd_did_options["seed"] = did_create.seed
        if did_create.network:
            create_cheqd_did_options["network"] = did_create.network
        # Notes:
        # - supported options: seed, network, verification_method
        # - key_type option is not implemented (default is ed25519)

        request = CreateCheqdDIDRequest(options=create_cheqd_did_options)
        logger.debug("Creating cheqd DID: `{}`", request)
        cheqd_did_response = await handle_acapy_call(
            logger=logger,
            acapy_call=controller.did.did_cheqd_create_post,
            body=request,
        )
        verkey = cheqd_did_response.verkey
        did = cheqd_did_response.did

        # Note: neither `success` nor `did_state` is populated in the response

        if not verkey or not did:
            logger.error("Failed to create cheqd DID: `{}`.", cheqd_did_response)
            raise CloudApiException("Error creating cheqd did.")

        result = DID(
            did=did,
            method="cheqd",
            verkey=verkey,
            key_type="ed25519",
            posture="posted",
        )
    else:
        did_response = await handle_acapy_call(
            logger=logger,
            acapy_call=controller.wallet.create_did,
            body=did_create.to_acapy_request(),
        )

        did_result = did_response.result
        if (
            not did_result or not did_result.did or not did_result.verkey
        ):  # pragma: no cover
            logger.error("Failed to create DID: `{}`.", did_response)
            raise CloudApiException("Error creating did.")
        result = did_result

    logger.debug("Successfully created local {} DID.", did_method)
    return result


async def set_public_did(
    controller: AcaPyClient,
    did: str,
    connection_id: str | None = None,
) -> DID:
    """Set the public did.

    Args:
        controller (AcaPyClient): aca-py client
        did (str): the did to set as public
        connection_id (str): the connection id to use to set the public did

    Raises:
        CloudApiException: if registration of the public did failed

    Returns:
        DID: the did

    """
    logger.debug("Setting public DID")
    did_response = await handle_acapy_call(
        logger=logger,
        acapy_call=controller.wallet.set_public_did,
        did=did,
        conn_id=connection_id,
        create_transaction_for_endorser=False,
    )

    result = did_response.result
    if not result:
        raise CloudApiException(f"Error setting public did to `{did}`.", 400)

    logger.debug("Successfully set public DID.")
    return result


async def get_public_did(controller: AcaPyClient) -> DID:
    """Get the public did.

    Args:
        controller (AcaPyClient): aca-py client

    Raises:
        CloudApiException: if retrieving the public did failed.

    Returns:
        DID: the public did

    """
    logger.debug("Fetching public DID")
    did_response = await handle_acapy_call(
        logger=logger, acapy_call=controller.wallet.get_public_did
    )

    result = did_response.result
    if not result:
        raise CloudApiException("No public did found", 404)

    logger.debug("Successfully fetched public DID.")
    return result
