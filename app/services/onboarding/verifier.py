from aries_cloudcontroller import AcaPyClient, InvitationCreateRequest, InvitationRecord

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.tenants import OnboardResult
from app.services import acapy_wallet
from app.util.did import qualified_did_sov
from shared.log_config import get_logger

logger = get_logger(__name__)


async def onboard_verifier(*, verifier_controller: AcaPyClient, verifier_label: str):
    """Onboard the controller as verifier.

    The onboarding will take care of the following:
      - create a multi_use invitation to use in the

    Args:
        verifier_controller (AcaPyClient): authenticated ACA-Py client for verifier
        verifier_label (str): alias for the verifier

    """
    bound_logger = logger.bind(body={"verifier_label": verifier_label})
    bound_logger.info("Onboarding verifier")

    onboarding_result = {}

    # If the verifier already has a public did it doesn't need an invitation. The invitation
    # is just to bypass having to pay for a public did for every verifier
    try:
        bound_logger.debug("Getting public DID for to-be verifier")
        public_did = await acapy_wallet.get_public_did(controller=verifier_controller)

        onboarding_result["did"] = qualified_did_sov(public_did.did)
    except CloudApiException:
        bound_logger.info(
            "No public DID found for to-be verifier. "
            "Creating OOB invitation on their behalf."
        )
        # create a multi_use invitation from the did
        request_body = InvitationCreateRequest(
            use_public_did=False,
            alias=f"Trust Registry {verifier_label}",
            handshake_protocols=["https://didcomm.org/didexchange/1.1"],
        )
        invitation: InvitationRecord = await handle_acapy_call(
            logger=logger,
            acapy_call=verifier_controller.out_of_band.create_invitation,
            auto_accept=True,
            multi_use=True,
            body=request_body,
        )

        # check if invitation and necessary attributes exist
        if invitation and invitation.invitation and invitation.invitation.services:
            try:
                # Because we're not creating an invitation with a public did the invitation will always
                # contain a did:key as the first recipientKey in the first service
                bound_logger.debug("Getting DID from verifier's invitation")
                service = invitation.invitation.services[0]
                if (
                    service
                    and "recipientKeys" in service
                    and len(service["recipientKeys"]) > 0
                ):
                    did = service["recipientKeys"][0]
                    if "#" in did:
                        did = did.split("#")[0]
                    onboarding_result["did"] = did
                else:
                    raise KeyError(  # pylint: disable=W0707
                        f"RecipientKeys not present in the invitation service: `{service}`."
                    )
                onboarding_result["didcomm_invitation"] = invitation.invitation_url
            except (KeyError, IndexError) as e:
                bound_logger.error(
                    "Created invitation does not contain expected keys: {}", e
                )
                raise CloudApiException(
                    "Error onboarding verifier: No public DID found. "
                    "Tried to create invitation, but found no service/recipientKeys."
                ) from e
        else:
            bound_logger.error(
                "Created invitation does not have necessary attributes. Got: `{}`.",
                invitation,
            )
            raise CloudApiException(  # pylint: disable=W0707
                "Error onboarding verifier: No public DID found. "
                "Tried and failed to create invitation on their behalf."
            ) from None

    bound_logger.debug("Returning verifier onboard result.")
    return OnboardResult(**onboarding_result)
