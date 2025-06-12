from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.dependencies.acapy_clients import TENANT_ADMIN_AUTHED
from app.routes.admin.tenants import get_tenants

wallet_id = "some_wallet_id"
wallet_name = "some_wallet_name"


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_get_tenants_success(group_id) -> None:
    # Setup wallets return object including the group_id it belongs to
    wallets_return_obj = AsyncMock()
    wallets_return_obj.results = ["some_wallets", "and_another_one", "why_not_another"]

    # Mock the get_wallets call to return the above object
    multitenancy_mock = AsyncMock(
        get_wallets=AsyncMock(return_value=wallets_return_obj)
    )
    admin_controller_mock = AsyncMock(multitenancy=multitenancy_mock)

    # Patch the dependencies
    with (
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
        patch(
            "app.routes.admin.tenants.tenant_from_wallet_record",
            return_value=Mock(),
        ) as mock_tenant_from_wallet_record,
    ):
        # Configure get_tenant_admin_controller to return our mocked admin_controller on enter
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            admin_controller_mock
        )

        # Execute the function under test
        await get_tenants(
            wallet_name=wallet_name,
            group_id=group_id,
            admin_auth=TENANT_ADMIN_AUTHED,
        )
        assert mock_tenant_from_wallet_record.call_count == len(
            wallets_return_obj.results
        )


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_get_tenants_success_no_wallets(group_id) -> None:
    # Setup wallets return object to be an empty list
    wallets_return_obj = AsyncMock()
    wallets_return_obj.results = []

    # Mock the get_wallets call to return the above object
    multitenancy_mock = AsyncMock(
        get_wallets=AsyncMock(return_value=wallets_return_obj)
    )
    admin_controller_mock = AsyncMock(multitenancy=multitenancy_mock)

    # Patch the dependencies
    with (
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
        patch(
            "app.routes.admin.tenants.tenant_from_wallet_record",
            return_value=Mock(),
        ) as mock_tenant_from_wallet_record,
    ):
        # Configure get_tenant_admin_controller to return our mocked admin_controller on enter
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            admin_controller_mock
        )

        # Execute the function under test
        await get_tenants(
            wallet_name=wallet_name,
            group_id=group_id,
            admin_auth=TENANT_ADMIN_AUTHED,
        )
        mock_tenant_from_wallet_record.assert_not_called()
