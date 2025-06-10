from typing import Any

from aries_cloudcontroller import AcaPyClient
from httpx import AsyncHTTPTransport

from shared import RichAsyncClient
from shared.constants import (
    GOVERNANCE_ACAPY_API_KEY,
    GOVERNANCE_AGENT_URL,
    GOVERNANCE_FASTAPI_ENDPOINT,
    TENANT_ACAPY_API_KEY,
    TENANT_ADMIN_FASTAPI_ENDPOINT,
    TENANT_AGENT_URL,
    TENANT_FASTAPI_ENDPOINT,
    TEST_CLIENT_TIMEOUT,
)


def get_common_settings(api_key: str) -> dict[str, Any]:
    return {
        "timeout": TEST_CLIENT_TIMEOUT,
        "headers": {
            "x-api-key": api_key,
            "content-type": "application/json",
        },
        "transport": AsyncHTTPTransport(retries=3),
    }


# Governance Clients
def get_governance_client() -> RichAsyncClient:
    settings = get_common_settings(f"governance.{GOVERNANCE_ACAPY_API_KEY}")
    return RichAsyncClient(
        base_url=GOVERNANCE_FASTAPI_ENDPOINT, name="Governance", **settings
    )


def get_governance_acapy_client() -> AcaPyClient:
    return AcaPyClient(base_url=GOVERNANCE_AGENT_URL, api_key=GOVERNANCE_ACAPY_API_KEY)


# Tenant Admin Clients
def get_tenant_admin_client() -> RichAsyncClient:
    settings = get_common_settings(f"tenant-admin.{TENANT_ACAPY_API_KEY}")
    return RichAsyncClient(
        base_url=TENANT_ADMIN_FASTAPI_ENDPOINT, name="Tenant Admin", **settings
    )


def get_tenant_admin_acapy_client() -> AcaPyClient:
    return AcaPyClient(base_url=TENANT_AGENT_URL, api_key=TENANT_ACAPY_API_KEY)


# Tenant Clients
def get_tenant_client(*, token: str, name: str = "") -> RichAsyncClient:
    settings = get_common_settings(token)
    return RichAsyncClient(
        base_url=TENANT_FASTAPI_ENDPOINT, name=f"Tenant {name}", **settings
    )


def get_tenant_acapy_client(*, token: str) -> AcaPyClient:
    return AcaPyClient(
        base_url=TENANT_AGENT_URL,
        api_key=TENANT_ACAPY_API_KEY,
        tenant_jwt=token,
    )
