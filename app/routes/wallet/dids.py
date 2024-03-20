from typing import List, Optional

from aries_cloudcontroller import DID, DIDCreate, DIDEndpoint, DIDEndpointWithType
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth
from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.wallet import SetDidEndpointRequest
from app.services import acapy_wallet
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/wallet/dids", tags=["wallet"])


@router.post("", response_model=DID)
async def create_did(
    did_create: Optional[DIDCreate] = None,
    auth: AcaPyAuth = Depends(acapy_auth),
):
    """Create Local DID."""
    logger.info("POST request received: Create DID")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Creating DID")
        result = await acapy_wallet.create_did(
            did_create=did_create, controller=aries_controller
        )

    logger.info("Successfully created DID.")
    return result


@router.get("", response_model=List[DID])
async def list_dids(
    auth: AcaPyAuth = Depends(acapy_auth),
) -> List[DID]:
    """
    Retrieve list of DIDs.
    """
    logger.info("GET request received: Retrieve list of DIDs")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching DIDs")
        did_result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_dids
        )

    if not did_result.results:
        logger.info("No DIDs returned.")
        return []

    logger.info("Successfully fetched list of DIDs.")
    return did_result.results


@router.get("/public", response_model=DID)
async def get_public_did(
    auth: AcaPyAuth = Depends(acapy_auth),
) -> DID:
    """
    Fetch the current public DID.
    """
    logger.info("GET request received: Fetch public DID")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching public DID")
        result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_public_did
        )

    if not result.result:
        logger.info("Bad request: no public DID found.")
        raise CloudApiException("No public did found.", 404)

    logger.info("Successfully fetched public DID.")
    return result.result


@router.put("/public", response_model=DID)
async def set_public_did(
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth),
) -> DID:
    """Set the current public DID."""
    logger.info("PUT request received: Set public DID")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Setting public DID")
        result = await acapy_wallet.set_public_did(aries_controller, did)

    logger.info("Successfully set public DID.")
    return result


@router.patch("/{did}/rotate-keypair", status_code=204)
async def rotate_keypair(
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth),
) -> None:
    bound_logger = logger.bind(body={"did": did})
    bound_logger.info("PATCH request received: Rotate keypair for DID")
    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Rotating keypair")
        await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.rotate_keypair, did=did
        )

    bound_logger.info("Successfully rotated keypair.")


@router.get("/{did}/endpoint", response_model=DIDEndpoint)
async def get_did_endpoint(
    did: str,
    auth: AcaPyAuth = Depends(acapy_auth),
) -> DIDEndpoint:
    """Get DID endpoint."""
    bound_logger = logger.bind(body={"did": did})
    bound_logger.info("GET request received: Get endpoint for DID")
    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching DID endpoint")
        result = await handle_acapy_call(
            logger=logger, acapy_call=aries_controller.wallet.get_did_endpoint, did=did
        )

    bound_logger.info("Successfully fetched DID endpoint.")
    return result


@router.post("/{did}/endpoint", status_code=204)
async def set_did_endpoint(
    did: str,
    body: SetDidEndpointRequest,
    auth: AcaPyAuth = Depends(acapy_auth),
) -> None:
    """Update Endpoint in wallet and on ledger if posted to it."""

    # "Endpoint" type is for making connections using public indy DIDs
    bound_logger = logger.bind(body={"did": did, "body": body})
    bound_logger.info("POST request received: Get endpoint for DID")

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

    bound_logger.info("Successfully set DID endpoint.")
