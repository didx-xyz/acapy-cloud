import os
from typing import Literal

from aries_cloudcontroller import DID, AcaPyClient, InvitationCreateRequest

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.tenants import OnboardResult
from app.models.wallet import DIDCreate
from app.services import acapy_wallet
from shared.log_config import get_logger

logger = get_logger(__name__)

MAIN_NET = os.getenv("MAIN_NET", "false").lower() == "true"


async def onboard_issuer(
    *,
    issuer_controller: AcaPyClient,
    issuer_wallet_id: str,
    issuer_label: str,
) -> OnboardResult:
    """Onboard the controller as issuer.

    The onboarding will make sure the issuer has a public did.

    Args:
        issuer_controller (AcaPyClient): authenticated ACA-Py client for issuer
        issuer_wallet_id (str): wallet id of the issuer
        issuer_label (str): alias for the issuer

    Returns:
        OnboardResult: The result of the onboarding process

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

    if not invitation.invitation_url:  # pragma: no cover
        bound_logger.error("Invitation URL not returned after creating invitation")
        raise CloudApiException("Invitation URL not found after creating invitation")

    return OnboardResult(
        did=issuer_did.did,
        didcomm_invitation=invitation.invitation_url,
    )


async def onboard_issuer_no_public_did(
    issuer_controller: AcaPyClient,
    issuer_wallet_id: str,
    issuer_label: str,
    did_method: Literal["cheqd"] = "cheqd",
) -> DID:
    """Onboard an issuer without a public DID.

    This function handles the case where the issuer does not have a public DID.
    It takes care of registering the issuer DID on the ledger.

    Args:
        issuer_label (str): Alias of the issuer
        issuer_controller (AcaPyClient): Authenticated ACA-Py client for issuer
        issuer_wallet_id (str): Wallet id of the issuer
        did_method (Literal["cheqd"]): DID method to use for onboarding the issuer

    Returns:
        issuer_did (DID): The issuer's DID after completing the onboarding process

    """
    bound_logger = logger.bind(
        body={"issuer_label": issuer_label, "issuer_wallet_id": issuer_wallet_id}
    )
    bound_logger.debug("Onboarding issuer that has no public DID")

    if MAIN_NET:
        did_create = DIDCreate(
            method=did_method,
            network="mainnet",
        )
    else:
        did_create = DIDCreate(method=did_method)

    issuer_did = await acapy_wallet.create_did(issuer_controller, did_create=did_create)

    bound_logger.debug("Successfully registered DID for issuer: {}.", issuer_did)
    return issuer_did
