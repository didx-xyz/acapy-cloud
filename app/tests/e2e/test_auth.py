import asyncio

import pytest
from aries_cloudcontroller import AcaPyClient
from aries_cloudcontroller.exceptions import UnauthorizedException
from uuid_utils import uuid4

from app.routes.admin.tenants import router as tenants_router
from app.routes.connections import router as connections_router
from app.tests.util.regression_testing import TestMode
from shared.constants import TENANT_FASTAPI_ENDPOINT
from shared.util.rich_async_client import RichAsyncClient

CONNECTIONS_BASE_PATH = connections_router.prefix
TENANTS_BASE_PATH = tenants_router.prefix

group_id = "TestGroup"

skip_regression_test_reason = "Don't need to cover auth tests in regression mode"


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
@pytest.mark.anyio
async def test_invalid_acapy_auth_header(alice_acapy_client: AcaPyClient) -> None:
    # Modify the AcaPyClient to use the wrong header -- assert ACA-Py auth error
    existing_token = alice_acapy_client.api_client.default_headers[
        "Authorization"
    ].split(" ")[1]

    alice_acapy_client.api_client.default_headers["Authorization"] = (
        f"Barer {existing_token}"
    )

    with pytest.raises(UnauthorizedException) as exc_info:
        await alice_acapy_client.connection.get_connections()
    assert exc_info.value.status == 401
    assert "Invalid Authorization header structure" == str(exc_info.value.reason)


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_jwt_invalid_token_error(tenant_admin_client: RichAsyncClient) -> None:
    # Step 1: Create a tenant and get a valid access token
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.example.com",
            "wallet_label": uuid4().hex,
            "group_id": group_id,
        },
    )
    assert response.status_code == 200
    tenant = response.json()
    wallet_id = tenant["wallet_id"]
    valid_token = tenant["access_token"].split("tenant.")[1]

    try:
        # Step 2: Corrupt the token
        # Split the token into header, payload, and signature
        token_parts = valid_token.split(".")
        assert len(token_parts) == 3, "Invalid JWT token format"

        # Corrupt the payload by altering a character
        corrupted_payload = token_parts[1][:-1] + (
            "A" if token_parts[1][-1] != "A" else "B"
        )
        corrupted_token = ".".join([token_parts[0], corrupted_payload, token_parts[2]])

        # Step 3: Attempt to use the corrupted token
        tenant_client = RichAsyncClient(
            base_url=TENANT_FASTAPI_ENDPOINT, raise_status_error=False
        )
        tenant_client.headers["x-api-key"] = f"tenant.{corrupted_token}"

        # Make a request to a protected endpoint
        response = await tenant_client.get(CONNECTIONS_BASE_PATH)

        # Step 4: Assert that the response is 401 Unauthorized
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"

    finally:
        # Cleanup: Delete the created tenant
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_invalid_token_error_after_rotation(
    tenant_admin_client: RichAsyncClient,
) -> None:
    # Step 1: Create a tenant and get a valid access token
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.example.com",
            "wallet_label": uuid4().hex,
            "group_id": group_id,
        },
    )
    assert response.status_code == 200
    tenant = response.json()
    wallet_id = tenant["wallet_id"]
    old_token = tenant["access_token"]

    # Prepare the tenant client and set header to original token
    tenant_client = RichAsyncClient(
        base_url=TENANT_FASTAPI_ENDPOINT, raise_status_error=False
    )
    tenant_client.headers["x-api-key"] = old_token

    try:
        # Step 2: Rotate the token once
        rotate_response = await tenant_admin_client.post(
            f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id={group_id}"
        )
        assert rotate_response.status_code == 200

        await asyncio.sleep(1)  # short sleep, because this test is very flaky

        # Rotate the token again
        rotate_response = await tenant_admin_client.post(
            f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id={group_id}"
        )
        assert rotate_response.status_code == 200

        await asyncio.sleep(4)  # sleep, allow for storage record to update

        # Step 3: Attempt to use the first token after token rotated
        response = await tenant_client.get(CONNECTIONS_BASE_PATH)

        # Step 4: Assert that the response is 401 Unauthorized
        assert response.status_code == 401
        assert response.json()["detail"] == "Token not valid."

    finally:
        # Cleanup: Delete the created tenant
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204
