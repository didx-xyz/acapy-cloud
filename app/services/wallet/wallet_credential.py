from logging import Logger

from aries_cloudcontroller import AcaPyClient

from app.exceptions.handle_acapy_call import handle_acapy_call
from app.models.verifier import Status
from app.models.wallet import CredInfoList


async def add_revocation_info(
    cred_info_list: CredInfoList,
    aries_controller: AcaPyClient,
    logger: Logger,
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
                    Status.REVOKED if rev_status.revoked else Status.VALID
                )
            except Exception as e:
                # Log the error and continue
                logger.error(
                    "Error fetching revocation status for {}: {}",
                    cred_info.credential_id,
                    e,
                )
                cred_info.revocation_status = Status.CHECK_FAILED
    return cred_info_list
    return cred_info_list
