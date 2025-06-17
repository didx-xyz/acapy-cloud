import base64
import json

from aries_cloudcontroller import AcaPyClient, WalletRecordWithGroupId
from fastapi import HTTPException

from app.dependencies.acapy_clients import get_tenant_admin_controller
from app.exceptions import handle_acapy_call
from app.exceptions.cloudapi_exception import CloudApiException
from app.models.tenants import Tenant
from shared.log_config import Logger


class WalletNotFoundException(HTTPException):
    """Class that represents a wallet was not found"""

    def __init__(self, wallet_id: str) -> None:
        """Initialize the wallet not found exception."""
        super().__init__(
            status_code=404, detail=f"Wallet with id `{wallet_id}` not found."
        )


def tenant_from_wallet_record(wallet_record: WalletRecordWithGroupId) -> Tenant:
    wallet_settings = wallet_record.settings or {}
    label: str = wallet_settings.get("default_label", "")
    wallet_name: str = wallet_settings.get("wallet.name", "")
    image_url: str | None = wallet_settings.get("image_url")
    group_id: str | None = wallet_settings.get("wallet.group_id")

    return Tenant(
        wallet_id=wallet_record.wallet_id,
        wallet_label=label,
        wallet_name=wallet_name,
        created_at=wallet_record.created_at,
        updated_at=wallet_record.updated_at,
        image_url=image_url,
        group_id=group_id,
    )


def get_wallet_id_from_b64encoded_jwt(jwt: str) -> str:
    # Add padding if required
    # b64 needs lengths divisible by 4
    if len(jwt) % 4 != 0:
        n_missing = 4 - (len(jwt) % 4)
        jwt = jwt + (n_missing * "=")

    wallet = json.loads(base64.b64decode(jwt))
    return wallet["wallet_id"]


async def get_wallet_label_from_controller(aries_controller: AcaPyClient) -> str:
    if not aries_controller.tenant_jwt:  # pragma: no cover
        raise CloudApiException("Cannot get wallet label from controller.", 404)
    controller_token = aries_controller.tenant_jwt.split(".")[1]
    controller_wallet_id = get_wallet_id_from_b64encoded_jwt(controller_token)
    async with get_tenant_admin_controller() as admin_controller:
        controller_wallet_record = await admin_controller.multitenancy.get_wallet(
            wallet_id=controller_wallet_id
        )
    controller_label = controller_wallet_record.settings["default_label"]
    return controller_label


async def get_wallet_and_assert_valid_group(
    admin_controller: AcaPyClient,
    wallet_id: str,
    group_id: str | None,
    logger: Logger,
) -> WalletRecordWithGroupId:
    """Fetch the wallet record for wallet_id, and assert it exists and belongs to group.

    Args:
        admin_controller (AcaPyClient): Admin AcaPyClient instance.
        wallet_id (str): The wallet_id we want to fetch.
        group_id (Optional[str]): The group_id to assert against.
        logger (Logger): A logger object.

    Raises:
        HTTPException: If the wallet does not exist or does not belong to group

    Returns:
        WalletRecordWithGroupId: When assertions pass, returns the wallet record.

    """
    logger.debug("Retrieving the wallet record for {}", wallet_id)
    wallet = await handle_acapy_call(
        logger=logger,
        acapy_call=admin_controller.multitenancy.get_wallet,
        wallet_id=wallet_id,
    )

    if not wallet:
        logger.info("Bad request: Wallet not found.")
        raise WalletNotFoundException(wallet_id=wallet_id)

    assert_valid_group(
        wallet=wallet, wallet_id=wallet_id, group_id=group_id, logger=logger
    )

    return wallet


def assert_valid_group(
    wallet: WalletRecordWithGroupId,
    wallet_id: str,
    group_id: str | None,
    logger: Logger,
) -> None:
    """Assert that wallet record belongs to group, and raise exception if not.

    Args:
        wallet (WalletRecordWithGroupId): The wallet record to check.
        wallet_id (str): The wallet id for the wallet record.
        group_id (Optional[str]): The group to validate against.
        logger (Logger): A logger object.

    Raises:
        HTTPException: If the wallet does not belong to the group_id.

    """
    wallet_group_id = (
        wallet.settings.get("wallet.group_id") if wallet.settings else None
    )
    if group_id and wallet_group_id != group_id:
        logger.info("Bad request: wallet_id does not belong to group_id.")

        # 404 instead of 403, obscure existence of wallet_id outside group
        raise WalletNotFoundException(wallet_id=wallet_id)

    logger.debug("Wallet {} belongs to group {}.", wallet_id, group_id)
