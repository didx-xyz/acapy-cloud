from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Response
from pytest_mock import MockerFixture

from app.models.tenants import CreateTenantResponse
from app.tests.util.client import (
    get_governance_client,
    get_tenant_admin_client,
    get_tenant_client,
)
from shared import RichAsyncClient
from shared.constants import TRUST_REGISTRY_FASTAPI_ENDPOINT


@pytest.fixture
async def trust_registry_client() -> AsyncGenerator[RichAsyncClient, Any]:
    async with RichAsyncClient(base_url=TRUST_REGISTRY_FASTAPI_ENDPOINT) as client:
        yield client


@pytest.fixture(scope="session")
async def governance_client() -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_governance_client() as gov_async_client:
        yield gov_async_client


@pytest.fixture(scope="function")
async def tenant_admin_client() -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_admin_client() as admin_async_client:
        yield admin_async_client


@pytest.fixture(scope="function")
async def alice_member_client(
    alice_tenant: CreateTenantResponse,
) -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_client(
        token=alice_tenant.access_token, name=alice_tenant.wallet_label
    ) as alice_async_client:
        yield alice_async_client


@pytest.fixture(scope="function")
async def bob_member_client(
    bob_tenant: CreateTenantResponse,
) -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_client(
        token=bob_tenant.access_token, name="Bob"
    ) as bob_async_client:
        yield bob_async_client


@pytest.fixture(scope="session")
async def faber_anoncreds_client(
    faber_anoncreds_issuer: CreateTenantResponse,
) -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_client(
        token=faber_anoncreds_issuer.access_token, name="Faber_anoncreds"
    ) as faber_async_client:
        yield faber_async_client


@pytest.fixture(scope="module")
async def acme_client(
    acme_verifier: CreateTenantResponse,
) -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_client(
        token=acme_verifier.access_token, name="Acme"
    ) as acme_async_client:
        yield acme_async_client


@pytest.fixture(scope="session")
async def meld_co_anoncreds_client(
    meld_co_anoncreds_issuer_verifier: CreateTenantResponse,
) -> AsyncGenerator[RichAsyncClient, Any]:
    async with get_tenant_client(
        token=meld_co_anoncreds_issuer_verifier.access_token, name="MeldCo_anoncreds"
    ) as meld_co_async_client:
        yield meld_co_async_client


@pytest.fixture
def mock_async_client(mocker: MockerFixture, request) -> Mock:
    """Patching RichAsyncClient in variable modules"""
    module_path = request.param
    patch_async_client = mocker.patch(f"{module_path}.RichAsyncClient")

    mocked_async_client = Mock()
    response = Response(status_code=200)
    mocked_async_client.get = AsyncMock(return_value=response)
    patch_async_client.return_value.__aenter__.return_value = mocked_async_client

    return mocked_async_client
