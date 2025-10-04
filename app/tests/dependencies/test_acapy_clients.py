from unittest.mock import Mock, patch

import pytest
from aries_cloudcontroller import AcaPyClient
from fastapi import HTTPException

from app.dependencies.acapy_clients import (
    AcaPyAuthVerified,
    client_from_auth,
    get_governance_controller,
    get_tenant_admin_controller,
    get_tenant_controller,
)
from app.dependencies.auth import AcaPyAuth
from app.dependencies.role import Role
from app.tests.util.client import get_tenant_acapy_client
from shared.constants import GOVERNANCE_ACAPY_API_KEY, TENANT_ACAPY_API_KEY


@pytest.mark.anyio
async def test_governance_agent(governance_acapy_client: AcaPyClient):
    assert isinstance(governance_acapy_client, AcaPyClient)
    assert (
        governance_acapy_client.configuration.host
        == Role.GOVERNANCE.agent_type.base_url
    )
    assert governance_acapy_client.api_key == GOVERNANCE_ACAPY_API_KEY
    assert "Authorization" not in governance_acapy_client.api_client.default_headers


@pytest.mark.anyio
async def test_tenant_agent():
    async with get_tenant_acapy_client(token="Alice") as alice_acapy_client:
        assert isinstance(alice_acapy_client, AcaPyClient)
        assert alice_acapy_client.configuration.host == Role.TENANT.agent_type.base_url
        assert (
            "Bearer " in alice_acapy_client.api_client.default_headers["Authorization"]
        )
        assert alice_acapy_client.api_key == TENANT_ACAPY_API_KEY


@pytest.mark.anyio
async def test_tenant_admin_agent(tenant_admin_acapy_client):
    assert isinstance(tenant_admin_acapy_client, AcaPyClient)
    assert tenant_admin_acapy_client.api_key == TENANT_ACAPY_API_KEY
    assert "Authorization" not in tenant_admin_acapy_client.api_client.default_headers


def test_get_governance_controller():
    with patch("app.dependencies.acapy_clients.AcaPyClient") as mock_acapy_client:
        get_governance_controller()
        mock_acapy_client.assert_called_with(
            base_url=Role.GOVERNANCE.agent_type.base_url,
            api_key=Role.GOVERNANCE.agent_type.x_api_key,
        )


def test_get_tenant_admin_controller():
    with patch("app.dependencies.acapy_clients.AcaPyClient") as mock_acapy_client:
        get_tenant_admin_controller()
        mock_acapy_client.assert_called_with(
            base_url=Role.TENANT_ADMIN.agent_type.base_url,
            api_key=Role.TENANT_ADMIN.agent_type.x_api_key,
        )


def test_get_tenant_controller():
    auth_token = "fake-jwt-token"
    with patch("app.dependencies.acapy_clients.AcaPyClient") as mock_acapy_client:
        get_tenant_controller(auth_token)
        mock_acapy_client.assert_called_with(
            base_url=Role.TENANT.agent_type.base_url,
            api_key=Role.TENANT.agent_type.x_api_key,
            tenant_jwt=auth_token,
        )


@pytest.mark.parametrize(
    "is_multitenant,is_admin",
    [
        (True, False),  # Multi-tenant but not admin
        (False, True),  # Admin but not multi-tenant
        (False, False),  # Neither admin nor multi-tenant
    ],
)
@pytest.mark.anyio
async def test_client_from_auth(is_multitenant, is_admin):
    auth = AcaPyAuthVerified(token="dummy-token", role=Mock(), wallet_id=Mock())
    auth.role.is_multitenant = is_multitenant
    auth.role.is_admin = is_admin
    auth.role.agent_type = Mock(x_api_key="api-key", base_url="base-url")

    async with client_from_auth(auth) as client:
        assert isinstance(client, AcaPyClient)


@pytest.mark.anyio
async def test_client_from_auth_missing_auth():
    with pytest.raises(HTTPException) as exc_info:
        async with client_from_auth(None):
            pass
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        async with client_from_auth(AcaPyAuth(token="", role=Role.TENANT)):
            pass
    assert exc_info.value.status_code == 403
