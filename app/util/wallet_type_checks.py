from logging import Logger
from typing import Literal

from aries_cloudcontroller import AcaPyClient

from app.dependencies.acapy_clients import get_tenant_admin_controller
from app.exceptions import CloudApiException, handle_acapy_call
from app.util.tenants import get_wallet_id_from_b64encoded_jwt


async def get_wallet_type(
    aries_controller: AcaPyClient, logger: Logger
) -> Literal["askar", "askar-anoncreds"]:
    """Check if the aries_controller has an anoncreds wallet.
    Args:
        aries_controller (AcaPyClient): The wallet controller to check.
        logger (Logger): A logger object.

    Returns:
        wallet_type: The wallet type of the controller.
    """
    controller_token = aries_controller.tenant_jwt.split(".")[1]
    controller_wallet_id = get_wallet_id_from_b64encoded_jwt(controller_token)
    async with get_tenant_admin_controller() as admin_controller:
        wallet = await handle_acapy_call(
            acapy_call=admin_controller.multitenancy.get_wallet,
            wallet_id=controller_wallet_id,
            logger=logger,
        )
        if not wallet:
            logger.info("Bad request: Wallet not found.")
            raise CloudApiException(status_code=401, detail="Wallet not found.")

        wallet_type = wallet.settings.get("wallet.type")

        if wallet_type not in ["askar", "askar-anoncreds"]:
            raise CloudApiException(status_code=401, detail="Invalid wallet type.")

        return wallet_type
