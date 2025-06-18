from aries_cloudcontroller import AcaPyClient

from app.exceptions.handle_acapy_call import handle_acapy_call
from app.models.verifier import RevocationStatus
from app.models.wallet import CredInfoList
from shared.log_config import get_logger

logger = get_logger(__name__)


async def add_revocation_info(
    cred_info_list: CredInfoList,
    aries_controller: AcaPyClient,
) -> CredInfoList:
    """Add revocation information to the credential info list."""
    for cred_info in cred_info_list.results or []:
        if cred_info.rev_reg_id and cred_info.cred_rev_id:
            try:
                # Fetch the revocation status
                rev_status = await handle_acapy_call(
                    logger=logger,
                    acapy_call=aries_controller.credentials.get_revocation_status,
                    credential_id=cred_info.credential_id,
                )
                cred_info.revocation_status = (
                    RevocationStatus.REVOKED
                    if rev_status.revoked
                    else RevocationStatus.ACTIVE
                )
            except Exception as e:
                # Log the error and continue
                logger.error(
                    "Error fetching revocation status for {}: {}",
                    cred_info.credential_id,
                    e,
                )
                cred_info.revocation_status = RevocationStatus.CHECK_FAILED
    return cred_info_list


async def check_non_revocable(
    cred_info_list: CredInfoList,
) -> CredInfoList:
    """Check if the credentials are non-revocable."""
    for cred_info in cred_info_list.results or []:
        if not cred_info.rev_reg_id or not cred_info.cred_rev_id:
            cred_info.revocation_status = None
            logger.debug(
                "Credential {} is non-revocable (no revocation registry or revocation ID)",
                cred_info.credential_id,
            )
    return cred_info_list
