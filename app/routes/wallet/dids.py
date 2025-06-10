from aries_cloudcontroller import DID, DIDEndpoint, DIDEndpointWithType
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.wallet import DIDCreate, SetDidEndpointRequest
from app.services import acapy_wallet
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/wallet/dids", tags=["wallet"])


@router.post("", response_model=DID, summary="Create Local DID")
async def create_did(
    did_create: DIDCreate | None = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> DID:
    """Create Local DID
    ---

    This endpoint allows you to create a new DID in the wallet.
    The `method` parameter is optional and can be set to
    'cheqd', 'key', 'web', 'did:peer:2', or 'did:peer:4'.

    Request Body:
    ---
        DIDCreate (Optional):
            method (str, optional): Method for the requested DID.
            seed (str, optional): Optional seed for DID.
            key_type (str, optional): Key type for the DID.
            did (str, optional): Specific DID value.

    Response:
    ---
        Returns the created DID object.
    """
    logger.debug("POST request received: Create DID with data: {}", did_create)

    if not did_create:
        did_create = DIDCreate()

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Creating DID with request: {}", did_create)
        result = await acapy_wallet.create_did(
            controller=aries_controller, did_create=did_create
        )

    logger.debug("Successfully created DID.")
    return result


@router.get("", response_model=list[DID], summary="List DIDs")
async def list_dids(
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> list[DID]:
    """Retrieve List of DIDs
    ---

    This endpoint allows you to retrieve a list of DIDs in the wallet.

    Response:
    ---
        Returns a list of DID objects.
    """
    logger.debug("GET request received: Retrieve list of DIDs")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching DIDs")
        did_result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_dids
        )

    if not did_result.results:
        logger.debug("No DIDs returned.")
        return []

    logger.debug("Successfully fetched list of DIDs.")
    return did_result.results


@router.get("/public", response_model=DID, summary="Fetch Public DID")
async def get_public_did(
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> DID:
    """Fetch the Current Public DID
    ---

    This endpoint allows you to fetch the current public DID.
    By default, only issuers will have public DIDs.

    Response:
    ---
        Returns the public DID.
    """
    logger.debug("GET request received: Fetch public DID")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching public DID")
        result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_public_did
        )

    if not result.result:
        raise CloudApiException("No public did found.", 404)

    logger.debug("Successfully fetched public DID.")
    return result.result


@router.put("/public", response_model=DID, summary="Set Public DID")
async def set_public_did(  # noqa: D417
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> DID:
    """Set the Current Public DID
    ---

    This endpoint allows you to set the current public DID.

    **Note:**
        - By default, only issuers can have and update public DIDs.

    Parameters
    ----------
        did: str

    Response:
    ---
        Returns the public DID.

    """
    logger.debug("PUT request received: Set public DID")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Setting public DID")
        result = await acapy_wallet.set_public_did(aries_controller, did)

    logger.debug("Successfully set public DID.")
    return result


@router.patch("/{did}/rotate-keypair", status_code=204, summary="Rotate Key Pair")
async def rotate_keypair(  # noqa: D417
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """Rotate Key Pair for DID
    ---

    This endpoint allows you to rotate the key pair for a DID.

    Parameters
    ----------
        did: str

    Response:
    ---
        204 No Content

    """
    bound_logger = logger.bind(body={"did": did})
    bound_logger.debug("PATCH request received: Rotate keypair for DID")
    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Rotating key pair")
        await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.rotate_keypair, did=did
        )

    bound_logger.debug("Successfully rotated keypair.")


@router.get("/{did}/endpoint", response_model=DIDEndpoint, summary="Get DID Endpoint")
async def get_did_endpoint(  # noqa: D417
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> DIDEndpoint:
    """Get DID Endpoint
    ---

    This endpoint allows you to fetch the endpoint for a DID.

    Parameters
    ----------
        did: str

    Response:
    ---
        Returns the endpoint for the DID.

    """
    bound_logger = logger.bind(body={"did": did})
    bound_logger.debug("GET request received: Get endpoint for DID")
    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching DID endpoint")
        result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_did_endpoint, did=did
        )

    bound_logger.debug("Successfully fetched DID endpoint.")
    return result


@router.post("/{did}/endpoint", status_code=204, summary="Set DID Endpoint")
async def set_did_endpoint(  # noqa: D417
    did: str,
    body: SetDidEndpointRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """Update Endpoint of DID in Wallet (and on Ledger, if it is a Public DID)
    ---

    This endpoint allows you to update the endpoint for a DID.

    Parameters
    ----------
        did: str

    Request Body:
    ---
        SetDidEndpointRequest:
            endpoint: str

    """
    # "Endpoint" type is for making connections using public DIDs
    bound_logger = logger.bind(body={"did": did, "body": body})
    bound_logger.debug("POST request received: Get endpoint for DID")

    endpoint_type = "Endpoint"

    request_body = handle_model_with_validation(
        logger=bound_logger,
        model_class=DIDEndpointWithType,
        did=did,
        endpoint=body.endpoint,
        endpoint_type=endpoint_type,
    )

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Setting DID endpoint")
        await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.wallet.set_did_endpoint,
            body=request_body,
        )

    bound_logger.debug("Successfully set DID endpoint.")
