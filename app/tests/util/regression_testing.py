import os
from typing import AsyncGenerator

from app.models.tenants import CreateTenantRequest, CreateTenantResponse
from app.tests.util.tenants import TENANT_BASE_PATH, delete_tenant, post_tenant_request
from shared.util.rich_async_client import RichAsyncClient


class RegressionTestConfig:
    group_id_prefix = "RegressionTests"

    reused_connection_alias = "RegressionTestConnection"

    run_regression_tests = os.getenv("RUN_REGRESSION_TESTS", "false").upper() == "TRUE"
    fail_on_recreating_fixtures = (
        os.getenv("FAIL_ON_RECREATING_FIXTURES", "false").upper() == "TRUE"
    )
    delete_fixtures_after_run = (
        os.getenv("DELETE_REGRESSION_FIXTURES", "false").upper() == "TRUE"
    )


class TestMode:
    clean_run = "clean"
    regression_run = "reuse"

    fixture_params = (
        [regression_run] if RegressionTestConfig.run_regression_tests else [clean_run]
    )


def assert_fail_on_recreating_fixtures(extra_context: str = ""):
    assert RegressionTestConfig.fail_on_recreating_fixtures is False, (
        f"Fixture is being recreated. {extra_context}"
    )


async def get_or_create_tenant(
    admin_client: RichAsyncClient,
    name: str,
    roles: list[str],
) -> CreateTenantResponse:
    group_id = f"{RegressionTestConfig.group_id_prefix}-{name}"

    list_tenants = (
        await admin_client.get(TENANT_BASE_PATH, params={"group_id": group_id})
    ).json()

    # Try to find the tenant by the specific role or name
    for tenant in list_tenants:
        if tenant.get("wallet_label") == name:
            # get access token and append to tenant, as it's required for CreateTenantResponse model
            access_token_response = await admin_client.post(
                f"{TENANT_BASE_PATH}/{tenant['wallet_id']}/access-token",
                params={"group_id": group_id},
            )
            access_token = access_token_response.json()["access_token"]
            tenant.update({"access_token": access_token})
            # Return existing tenant if found
            return CreateTenantResponse.model_validate(tenant)

    assert_fail_on_recreating_fixtures()

    # If not found, create a new tenant
    request = CreateTenantRequest(wallet_label=name, group_id=group_id, roles=roles)
    return await post_tenant_request(admin_client, request)


async def get_or_create_tenant_with_delete_check(
    admin_client: RichAsyncClient,
    name: str,
    roles: list[str],
) -> AsyncGenerator[CreateTenantResponse, None]:
    tenant = await get_or_create_tenant(
        admin_client=admin_client, name=name, roles=roles
    )
    try:
        yield tenant
    finally:
        if RegressionTestConfig.delete_fixtures_after_run:
            await delete_tenant(admin_client, tenant.wallet_id)
