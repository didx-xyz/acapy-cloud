from aries_cloudcontroller import DID, AcaPyClient, InvitationCreateRequest

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.tenants import OnboardResult
from app.services import acapy_wallet
from app.services.onboarding.util.register_issuer_did import (
    create_connection_with_endorser,
    register_issuer_did,
)
from app.util.did import qualified_did_sov
from shared.log_config import get_logger

logger = get_logger(__name__)


async def onboard_issuer(
    *,
    endorser_controller: AcaPyClient,
    issuer_controller: AcaPyClient,
    issuer_wallet_id: str,
    issuer_label: str = None,
) -> OnboardResult:
    """Onboard the controller as issuer.

    The onboarding will take care of the following:
      - make sure the issuer has a public did
      - make sure the issuer has a connection with the endorser
      - make sure the issuer has set up endorsement with the endorser connection

    Args:
        issuer_controller (AcaPyClient): authenticated ACA-Py client for issuer
        endorser_controller (AcaPyClient): authenticated ACA-Py client for endorser
        issuer_label (str): alias for the issuer
    """
    bound_logger = logger.bind(
        body={"issuer_label": issuer_label, "issuer_wallet_id": issuer_wallet_id}
    )
    bound_logger.debug("Onboarding issuer")

    try:
        issuer_did = await acapy_wallet.get_public_did(controller=issuer_controller)
        bound_logger.debug("Obtained public DID for the to-be issuer")
    except CloudApiException:
        bound_logger.debug("No public DID for the to-be issuer")
        issuer_did = await onboard_issuer_no_public_did(
            endorser_controller=endorser_controller,
            issuer_controller=issuer_controller,
            issuer_wallet_id=issuer_wallet_id,
            issuer_label=issuer_label,
        )

    bound_logger.debug("Creating OOB invitation on behalf of issuer")
    request_body = InvitationCreateRequest(
        alias=f"Trust Registry {issuer_label}",
        handshake_protocols=["https://didcomm.org/didexchange/1.1"],
    )
    invitation = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=issuer_controller.out_of_band.create_invitation,
        auto_accept=True,
        multi_use=True,
        body=request_body,
    )

    return OnboardResult(
        did=qualified_did_sov(issuer_did.did),
        didcomm_invitation=invitation.invitation_url,
    )


async def onboard_issuer_no_public_did(
    endorser_controller: AcaPyClient,
    issuer_controller: AcaPyClient,
    issuer_wallet_id: str,
    issuer_label: str,
) -> DID:
    """
    Onboard an issuer without a public DID.

    This function handles the case where the issuer does not have a public DID.
    It takes care of the following steps:
      - Create an endorser invitation using the endorser_controller
      - Wait for the connection between issuer and endorser to complete
      - Set roles for both issuer and endorser
      - Configure endorsement for the connection
      - Register the issuer DID on the ledger

    Args:
        issuer_label (str): Alias of the issuer
        endorser_controller (AcaPyClient): Authenticated ACA-Py client for endorser
        issuer_controller (AcaPyClient): Authenticated ACA-Py client for issuer
        issuer_wallet_id (str): Wallet id of the issuer

    Returns:
        issuer_did (DID): The issuer's DID after completing the onboarding process
    """
    bound_logger = logger.bind(
        body={"issuer_label": issuer_label, "issuer_wallet_id": issuer_wallet_id}
    )
    bound_logger.debug("Onboarding issuer that has no public DID")

    try:
        bound_logger.debug("Getting public DID for endorser")
        endorser_did = await acapy_wallet.get_public_did(controller=endorser_controller)
    except Exception as e:
        bound_logger.critical("Could not get endorser's public DID: {}", e)
        raise CloudApiException("Unable to get endorser public DID.") from e

    try:
        bound_logger.info("Creating connection with endorser")

        issuer_connection_id = await create_connection_with_endorser(
            endorser_controller=endorser_controller,
            issuer_controller=issuer_controller,
            endorser_did=endorser_did,
            name=issuer_label,
            logger=bound_logger,
        )

        issuer_did = await register_issuer_did(
            issuer_controller=issuer_controller,
            issuer_label=issuer_label,
            issuer_endorser_connection_id=issuer_connection_id,
            logger=bound_logger,
        )
    except Exception as e:
        bound_logger.exception("Could not create connection with endorser.")
        raise CloudApiException(
            f"Error creating connection with endorser: {str(e)}",
        ) from e

    bound_logger.debug("Successfully registered DID for issuer.")
    return issuer_did
