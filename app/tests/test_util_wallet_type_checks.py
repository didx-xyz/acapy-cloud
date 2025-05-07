from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.util.wallet_type_checks import (
    get_wallet_type,
)


@pytest.mark.anyio
async def test_get_wallet_type_askar():
    logger = MagicMock()
    aries_controller = MagicMock(spec=AcaPyClient)
    aries_controller.tenant_jwt = "header.payload.signature"

    with patch(
        "app.util.wallet_type_checks.get_wallet_id_from_b64encoded_jwt",
        return_value="wallet-id",
    ):
        with patch(
            "app.util.wallet_type_checks.get_tenant_admin_controller",
            new_callable=MagicMock(),
        ) as mock_get_tenant_admin_controller:
            admin_controller = (
                mock_get_tenant_admin_controller.return_value.__aenter__.return_value
            )
            admin_controller.multitenancy.get_wallet = AsyncMock(
                return_value=MagicMock(settings={"wallet.type": "askar"})
            )

            wallet_type = await get_wallet_type(aries_controller, logger)
            assert wallet_type == "askar"


@pytest.mark.anyio
async def test_get_wallet_type_askar_anoncreds():
    logger = MagicMock()
    aries_controller = MagicMock(spec=AcaPyClient)
    aries_controller.tenant_jwt = "header.payload.signature"

    with patch(
        "app.util.wallet_type_checks.get_wallet_id_from_b64encoded_jwt",
        return_value="wallet-id",
    ):
        with patch(
            "app.util.wallet_type_checks.get_tenant_admin_controller",
            new_callable=MagicMock,
        ) as mock_get_tenant_admin_controller:
            admin_controller = (
                mock_get_tenant_admin_controller.return_value.__aenter__.return_value
            )
            admin_controller.multitenancy.get_wallet = AsyncMock(
                return_value=MagicMock(settings={"wallet.type": "askar-anoncreds"})
            )

            wallet_type = await get_wallet_type(aries_controller, logger)
            assert wallet_type == "askar-anoncreds"


@pytest.mark.anyio
async def test_get_wallet_type_wallet_not_found():
    logger = MagicMock()
    aries_controller = MagicMock(spec=AcaPyClient)
    aries_controller.tenant_jwt = "header.payload.signature"

    with patch(
        "app.util.wallet_type_checks.get_wallet_id_from_b64encoded_jwt",
        return_value="wallet-id",
    ):
        with patch(
            "app.util.wallet_type_checks.get_tenant_admin_controller",
            new_callable=MagicMock,
        ) as mock_get_tenant_admin_controller:
            admin_controller = (
                mock_get_tenant_admin_controller.return_value.__aenter__.return_value
            )
            admin_controller.multitenancy.get_wallet = AsyncMock(return_value=None)

            with pytest.raises(CloudApiException) as exc:
                await get_wallet_type(aries_controller, logger)
            assert exc.value.status_code == 401
            assert exc.value.detail == "Wallet not found."


@pytest.mark.anyio
async def test_get_wallet_type_invalid_wallet_type():
    logger = MagicMock()
    aries_controller = MagicMock(spec=AcaPyClient)
    aries_controller.tenant_jwt = "header.payload.signature"

    with patch(
        "app.util.wallet_type_checks.get_wallet_id_from_b64encoded_jwt",
        return_value="wallet-id",
    ):
        with patch(
            "app.util.wallet_type_checks.get_tenant_admin_controller",
            new_callable=MagicMock,
        ) as mock_get_tenant_admin_controller:
            admin_controller = (
                mock_get_tenant_admin_controller.return_value.__aenter__.return_value
            )
            admin_controller.multitenancy.get_wallet = AsyncMock(
                return_value=MagicMock(settings={"wallet.type": "invalid"})
            )

            with pytest.raises(CloudApiException) as exc:
                await get_wallet_type(aries_controller, logger)
            assert exc.value.status_code == 401
            assert exc.value.detail == "Invalid wallet type."
