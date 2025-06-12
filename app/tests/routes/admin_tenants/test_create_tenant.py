from secrets import token_urlsafe
from unittest.mock import ANY, AsyncMock, patch

import base58
import pytest
from aries_cloudcontroller import CreateWalletRequestWithGroupId, CreateWalletResponse
from fastapi import HTTPException

from app.dependencies.acapy_clients import TENANT_ADMIN_AUTHED
from app.exceptions import CloudApiException, TrustRegistryException
from app.models.tenants import (
    CreateTenantRequest,
    OnboardResult,
)
from app.routes.admin.tenants import create_tenant
from shared.models.trustregistry import Actor

wallet_id = "some_wallet_id"
wallet_name = "some_wallet_name"

create_wallet_response = CreateWalletResponse(
    key_management_mode="managed",
    wallet_id=wallet_id,
    created_at="2024-02-27T09:48:39.508826Z",
    updated_at="2024-02-27T09:48:39.508826Z",
    token="abc",
)
create_tenant_body = CreateTenantRequest(
    wallet_label="Test Wallet",
    wallet_name=wallet_name,
    roles=["issuer"],
    group_id="test_group",
    image_url="some_image_url",
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "roles",
    [[], ["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_success(roles) -> None:
    # Create tenant request body
    body = create_tenant_body.model_copy(update={"roles": roles})
    wallet_label = create_tenant_body.wallet_label

    # Mock the dependencies
    mock_admin_controller = AsyncMock()
    mock_admin_controller.multitenancy.create_wallet = AsyncMock(
        return_value=create_wallet_response
    )

    did = "did:example:123"
    didcomm_invitation = "invitation_string"
    mock_onboard_tenant_result = OnboardResult(
        did=did, didcomm_invitation=didcomm_invitation
    )
    mock_onboard_tenant = AsyncMock(return_value=mock_onboard_tenant_result)

    mock_register_actor = AsyncMock()

    expected_wallet_body = CreateWalletRequestWithGroupId(
        image_url=body.image_url,
        key_management_mode="managed",
        label=wallet_label,
        wallet_key=base58.b58encode(token_urlsafe(48)).decode(),
        wallet_name=wallet_name,
        wallet_type="askar-anoncreds",
        group_id=body.group_id,
        extra_settings=body.extra_settings,
    )

    with (
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
        patch(
            "app.routes.admin.tenants.handle_model_with_validation",
            return_value=expected_wallet_body,
        ),
        patch(
            "app.services.onboarding.tenants.onboard_issuer",
            mock_onboard_tenant,
        ) as mock_onboard_issuer,
        patch(
            "app.services.onboarding.tenants.onboard_verifier",
            mock_onboard_tenant,
        ) as mock_onboard_verifier,
        patch("app.routes.admin.tenants.register_actor", mock_register_actor),
        patch("app.routes.admin.tenants.assert_actor_name", return_value=False),
    ):
        # Configure get_tenant_admin_controller to return our mocked admin_controller on enter
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            mock_admin_controller
        )

        response = await create_tenant(
            body=body,
            admin_auth=TENANT_ADMIN_AUTHED,
        )

        assert response.wallet_label == wallet_label
        assert response.group_id == create_tenant_body.group_id

        mock_admin_controller.multitenancy.create_wallet.assert_awaited_once_with(
            body=expected_wallet_body
        )

        if roles:
            mock_register_actor.assert_awaited_once_with(
                actor=Actor(
                    id=create_wallet_response.wallet_id,
                    name=create_tenant_body.wallet_label,
                    roles=roles,
                    did=did,
                    didcomm_invitation=didcomm_invitation,
                    image_url=create_tenant_body.image_url,
                )
            )
            if "issuer" in roles:
                mock_onboard_issuer.assert_awaited_once_with(
                    issuer_controller=ANY,
                    issuer_wallet_id=wallet_id,
                    issuer_label=wallet_label,
                )
            elif "verifier" in roles:
                mock_onboard_verifier.assert_awaited_once_with(
                    verifier_label=wallet_label,
                    verifier_controller=ANY,
                )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "roles",
    [[], ["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_fail_trust_registry_error(roles) -> None:
    with (
        patch(
            "app.routes.admin.tenants.assert_actor_name",
            side_effect=TrustRegistryException("Error"),
        ),
        pytest.raises(
            CloudApiException,
            match="An error occurred when trying to register actor. Please try again",
        ) as exc,
    ):
        await create_tenant(
            body=create_tenant_body.model_copy(update={"roles": roles}),
            admin_auth=TENANT_ADMIN_AUTHED,
        )
    assert exc.value.status_code == 500


@pytest.mark.anyio
@pytest.mark.parametrize(
    "roles",
    [[], ["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_fail_actor_exists(roles) -> None:
    wallet_label = "abc"
    with (
        patch(
            "app.routes.admin.tenants.assert_actor_name",
            return_value=True,
        ),
        pytest.raises(
            HTTPException,
            match=(
                f"Can't create Tenant. The label `{wallet_label}` may not "
                "be re-used because it exists on the trust registry."
            ),
        ) as exc,
    ):
        await create_tenant(
            body=create_tenant_body.model_copy(
                update={"roles": roles, "wallet_label": wallet_label}
            ),
            admin_auth=TENANT_ADMIN_AUTHED,
        )
    assert exc.value.status_code == 409


@pytest.mark.anyio
@pytest.mark.parametrize(
    "roles",
    [[], ["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_fail_wallet_name_exists(roles) -> None:
    with (
        patch(
            "app.routes.admin.tenants.handle_acapy_call",
            side_effect=CloudApiException(status_code=400, detail="already exists"),
        ),
        patch(
            "app.routes.admin.tenants.assert_actor_name",
            return_value=False,
        ),
        pytest.raises(
            HTTPException,
            match=(
                f"A wallet with name `{wallet_name}` already exists. "
                "The wallet name must be unique."
            ),
        ) as exc,
    ):
        await create_tenant(
            body=create_tenant_body.model_copy(update={"roles": roles}),
            admin_auth=TENANT_ADMIN_AUTHED,
        )
    assert exc.value.status_code == 409


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_msg", ["Error1", "Error2"])
@pytest.mark.parametrize(
    "roles",
    [[], ["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_fail_wallet_creation(
    status_code, error_msg, roles
) -> None:
    # Create tenant should raise the same error message / status code of create wallet failure
    with (
        patch(
            "app.routes.admin.tenants.handle_acapy_call",
            side_effect=CloudApiException(status_code=status_code, detail=error_msg),
        ),
        patch("app.routes.admin.tenants.assert_actor_name", return_value=False),
        pytest.raises(HTTPException, match=error_msg) as exc,
    ):
        await create_tenant(
            body=create_tenant_body.model_copy(update={"roles": roles}),
            admin_auth=TENANT_ADMIN_AUTHED,
        )
    assert exc.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception",
    [HTTPException(status_code=500, detail="Error"), Exception("Error")],
)
@pytest.mark.parametrize(
    "roles",
    [["issuer"], ["verifier"], ["issuer", "verifier"]],
)
async def test_create_tenant_fail_onboard_exception(exception, roles) -> None:
    mock_admin_controller = AsyncMock()
    mock_admin_controller.multitenancy.create_wallet = AsyncMock(
        return_value=create_wallet_response
    )
    mock_admin_controller.multitenancy.delete_wallet = AsyncMock()

    with (
        patch(
            "app.routes.admin.tenants.get_tenant_admin_controller"
        ) as mock_get_admin_controller,
        patch(
            "app.routes.admin.tenants.onboard_tenant",
            side_effect=exception,
        ) as mock_onboard,
        patch(
            "app.routes.admin.tenants.assert_actor_name",
            return_value=False,
        ),
        pytest.raises(type(exception), match="Error"),
    ):
        mock_get_admin_controller.return_value.__aenter__.return_value = (
            mock_admin_controller
        )
        await create_tenant(
            body=create_tenant_body.model_copy(update={"roles": roles}),
            admin_auth=TENANT_ADMIN_AUTHED,
        )

    # Assert created wallet is deleted if something went wrong in onboarding
    mock_onboard.assert_awaited_once()
    mock_admin_controller.multitenancy.delete_wallet.assert_awaited_once_with(
        wallet_id=wallet_id
    )
