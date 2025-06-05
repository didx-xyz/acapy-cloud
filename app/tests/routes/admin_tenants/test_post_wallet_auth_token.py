from unittest.mock import ANY, AsyncMock, patch

import pytest
from aries_cloudcontroller import CreateWalletTokenRequest
from fastapi import HTTPException

from app.dependencies.acapy_clients import TENANT_ADMIN_AUTHED
from app.routes.admin.tenants import post_wallet_auth_token

wallet_id = "some_wallet_id"
wallet_name = "some_wallet_name"


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_post_wallet_auth_token_success(group_id):
    # Mock the structure of admin_controller -> multitenancy -> get_auth_token
    multitenancy_mock = AsyncMock(get_auth_token=AsyncMock())
    admin_controller_mock = AsyncMock(multitenancy=multitenancy_mock)

    with (
        patch(
            "app.routes.admin.tenants.get_wallet_and_assert_valid_group",
            return_value=AsyncMock(),
        ) as mock_assert_valid_group,
        patch("app.routes.admin.tenants.fetch_actor_by_id", return_value=None),
        patch("app.routes.admin.tenants.remove_actor_by_id", return_value=AsyncMock()),
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
    ):
        # Configure get_tenant_admin_controller to return our mocked admin_controller on enter
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            admin_controller_mock
        )

        # Execute the function under test
        await post_wallet_auth_token(
            wallet_id=wallet_id, group_id=group_id, admin_auth=TENANT_ADMIN_AUTHED
        )

        mock_assert_valid_group.assert_awaited_once_with(
            admin_controller=admin_controller_mock,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=ANY,
        )

        # Assert that get_auth_token was called with the correct wallet_id
        admin_controller_mock.multitenancy.get_auth_token.assert_awaited_once_with(
            wallet_id=wallet_id, body=CreateWalletTokenRequest()
        )


@pytest.mark.anyio
async def test_post_wallet_auth_token_fail_wrong_group():
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
            await post_wallet_auth_token(
                wallet_id=wallet_id,
                group_id="wrong_group",
                admin_auth=TENANT_ADMIN_AUTHED,
            )

        assert exc_info.value.status_code == 404
        # Ensure the get_wallet was called as expected
        admin_controller_mock.multitenancy.get_wallet.assert_awaited_with(
            wallet_id=wallet_id
        )
