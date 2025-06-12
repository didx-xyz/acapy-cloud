from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.dependencies.acapy_clients import TENANT_ADMIN_AUTHED
from app.routes.admin.tenants import get_tenant

wallet_id = "some_wallet_id"
wallet_name = "some_wallet_name"


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_get_tenant_success(group_id) -> None:
    admin_controller_mock = AsyncMock()

    # Patch the dependencies
    with (
        patch(
            "app.routes.admin.tenants.get_wallet_and_assert_valid_group",
            return_value=AsyncMock(),
        ) as mock_assert_valid_group,
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
        patch(
            "app.routes.admin.tenants.tenant_from_wallet_record",
            return_value=Mock(),
        ),
    ):
        # Configure get_tenant_admin_controller to return our mocked admin_controller on enter
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            admin_controller_mock
        )

        # Execute the function under test
        await get_tenant(
            wallet_id=wallet_id,
            group_id=group_id,
            admin_auth=TENANT_ADMIN_AUTHED,
        )

        # Verify mocks were called as expected
        mock_assert_valid_group.assert_awaited_once_with(
            admin_controller=admin_controller_mock,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=ANY,
        )


@pytest.mark.anyio
async def test_get_tenant_fail_wrong_group() -> None:
    # Setup wallet return object including the group_id it belongs to
    wallet_return_obj = AsyncMock()
    wallet_return_obj.settings = {"wallet.group_id": "correct_group"}

    # Mock the get_wallet call to return the above object
    multitenancy_mock = AsyncMock(get_wallet=AsyncMock(return_value=wallet_return_obj))
    admin_controller_mock = AsyncMock(multitenancy=multitenancy_mock)

    with patch(
        "app.routes.admin.tenants.get_tenant_admin_controller"
    ) as mock_get_admin_controller:
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            admin_controller_mock
        )

        # Expect an HTTPException due to group mismatch
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant(
                wallet_id=wallet_id,
                group_id="wrong_group",
                admin_auth=TENANT_ADMIN_AUTHED,
            )

        assert exc_info.value.status_code == 404
        # Ensure the get_wallet was called as expected
        admin_controller_mock.multitenancy.get_wallet.assert_awaited_with(
            wallet_id=wallet_id
        )
