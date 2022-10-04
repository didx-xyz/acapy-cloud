import pytest

from app.tests.util.client import (
    governance_client as _governance_client,
    governance_acapy_client as _governance_acapy_client,
    tenant_admin_client as _tenant_admin_client,
    tenant_admin_acapy_client as _tenant_admin_acapy_client,
)

# governance


@pytest.yield_fixture(scope="module")
async def governance_acapy_client():
    client = _governance_acapy_client()
    yield client

    await client.close()


@pytest.yield_fixture(scope="module")
async def governance_client():
    async with _governance_client() as client:
        yield client


# TENANT ADMIN


@pytest.yield_fixture(scope="module")
async def tenant_admin_client():
    async with _tenant_admin_client() as client:
        yield client


@pytest.yield_fixture(scope="module")
async def tenant_admin_acapy_client():
    client = _tenant_admin_acapy_client()
    yield client

    await client.close()
