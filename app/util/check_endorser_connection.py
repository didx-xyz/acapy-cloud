from aries_cloudcontroller import AcaPyClient

from app.exceptions import handle_acapy_call
from shared.constants import ACAPY_ENDORSER_ALIAS
from shared.log_config import get_logger

logger = get_logger(__name__)


async def check_endorser_connection(aries_controller: AcaPyClient) -> bool:
    """
    Check if tenant has an active connection with the endorser.
    """
    logger.debug("Get connection by endorser alias")
    endorser_connection = await handle_acapy_call(
        logger=logger,
        acapy_call=aries_controller.connection.get_connections,
        alias=ACAPY_ENDORSER_ALIAS,
        state="completed",
    )

    has_connections = len(endorser_connection.results) > 0

    return has_connections
