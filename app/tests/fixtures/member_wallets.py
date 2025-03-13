from typing import Any, AsyncGenerator

import pytest

from app.models.tenants import CreateTenantResponse
from app.tests.util.client import get_tenant_admin_client
from app.tests.util.regression_testing import TestMode, get_or_create_tenant
from app.tests.util.tenants import (
    create_issuer_and_verifier_tenant,
    create_issuer_tenant,
    create_tenant,
    create_verifier_tenant,
    delete_tenant,
)


@pytest.fixture(scope="function", params=TestMode.fixture_params)
async def alice_tenant(request) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            tenant = await create_tenant(
                admin_client, name="alice", wallet_type="askar-anoncreds"
            )

            yield tenant

            await delete_tenant(admin_client, tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            tenant = await get_or_create_tenant(
                admin_client=admin_client, name="RegressionHolderAlice", roles=[]
            )

            yield tenant


@pytest.fixture(scope="function", params=TestMode.fixture_params)
async def bob_tenant(request) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            tenant = await create_tenant(
                admin_client, name="bob", wallet_type="askar-anoncreds"
            )

            yield tenant

            await delete_tenant(admin_client, tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            tenant = await get_or_create_tenant(
                admin_client=admin_client, name="RegressionHolderBob", roles=[]
            )

            yield tenant


@pytest.fixture(scope="module", params=TestMode.fixture_params)
async def acme_verifier(request) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            verifier_tenant = await create_verifier_tenant(
                admin_client, name="acme", wallet_type="askar-anoncreds"
            )

            yield verifier_tenant

            await delete_tenant(admin_client, verifier_tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            verifier_tenant = await get_or_create_tenant(
                admin_client=admin_client, name="RegressionVerifier", roles=["verifier"]
            )

            yield verifier_tenant


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def faber_indy_issuer(request) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            issuer_tenant = await create_issuer_tenant(
                admin_client, name="faber_indy", wallet_type="askar"
            )

            yield issuer_tenant

            await delete_tenant(admin_client, issuer_tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            issuer_tenant = await get_or_create_tenant(
                admin_client=admin_client, name="RegressionIssuer", roles=["issuer"]
            )

            yield issuer_tenant


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def faber_anoncreds_issuer(request) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            issuer_tenant = await create_issuer_tenant(
                admin_client, name="faber_anoncreds", wallet_type="askar-anoncreds"
            )

            yield issuer_tenant

            await delete_tenant(admin_client, issuer_tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            issuer_tenant = await get_or_create_tenant(
                admin_client=admin_client, name="RegressionIssuer", roles=["issuer"]
            )

            yield issuer_tenant


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def meld_co_indy_issuer_verifier(
    request,
) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            issuer_and_verifier_tenant = await create_issuer_and_verifier_tenant(
                admin_client, name="meldCo_indy", wallet_type="askar"
            )

            yield issuer_and_verifier_tenant

            await delete_tenant(admin_client, issuer_and_verifier_tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            issuer_tenant = await get_or_create_tenant(
                admin_client=admin_client,
                name="RegressionIssuerAndVerifier",
                roles=["issuer", "verifier"],
            )

            yield issuer_tenant


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def meld_co_anoncreds_issuer_verifier(
    request,
) -> AsyncGenerator[CreateTenantResponse, Any]:
    test_mode = request.param

    async with get_tenant_admin_client() as admin_client:
        if test_mode == TestMode.clean_run:
            issuer_and_verifier_tenant = await create_issuer_and_verifier_tenant(
                admin_client, name="meldCo_anoncreds", wallet_type="askar-anoncreds"
            )

            yield issuer_and_verifier_tenant

            await delete_tenant(admin_client, issuer_and_verifier_tenant.wallet_id)

        elif test_mode == TestMode.regression_run:
            issuer_tenant = await get_or_create_tenant(
                admin_client=admin_client,
                name="RegressionIssuerAndVerifier",
                roles=["issuer", "verifier"],
            )

            yield issuer_tenant
