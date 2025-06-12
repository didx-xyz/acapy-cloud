from collections.abc import AsyncGenerator
from typing import Any

import pytest
from aries_cloudcontroller import AcaPyClient

from app.tests.util.client import (
    get_governance_acapy_client,
    get_tenant_acapy_client,
    get_tenant_admin_acapy_client,
)
from shared import RichAsyncClient


@pytest.fixture(scope="session")
async def governance_acapy_client() -> AsyncGenerator[AcaPyClient, Any]:
    async with get_governance_acapy_client() as acapy_client:
        yield acapy_client


@pytest.fixture(scope="function")
async def tenant_admin_acapy_client() -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_admin_acapy_client() as acapy_client:
        yield acapy_client


def get_token(client: RichAsyncClient) -> str:
    # We extract the token from the x-api-key header as that's the easiest
    # method to create an AcaPyClient from an AsyncClient
    [_, token] = client.headers.get("x-api-key").split(".", maxsplit=1)
    return token


@pytest.fixture(scope="function")
async def alice_acapy_client(
    alice_member_client: RichAsyncClient,
) -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_acapy_client(
        token=get_token(alice_member_client)
    ) as acapy_client:
        yield acapy_client


@pytest.fixture(scope="function")
async def bob_acapy_client(
    bob_member_client: RichAsyncClient,
) -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_acapy_client(
        token=get_token(bob_member_client)
    ) as acapy_client:
        yield acapy_client


@pytest.fixture(scope="function")
async def faber_anoncreds_acapy_client(
    faber_anoncreds_client: RichAsyncClient,
) -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_acapy_client(
        token=get_token(faber_anoncreds_client)
    ) as acapy_client:
        yield acapy_client


@pytest.fixture(scope="function")
async def acme_acapy_client(
    acme_client: RichAsyncClient,
) -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_acapy_client(token=get_token(acme_client)) as acapy_client:
        yield acapy_client


@pytest.fixture(scope="module")
async def meld_co_anoncreds_acapy_client(
    meld_co_anoncreds_client: RichAsyncClient,
) -> AsyncGenerator[AcaPyClient, Any]:
    async with get_tenant_acapy_client(
        token=get_token(meld_co_anoncreds_client)
    ) as acapy_client:
        yield acapy_client
