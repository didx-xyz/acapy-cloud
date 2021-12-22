from typing import Any, Optional
from aries_cloudcontroller.acapy_client import AcaPyClient
from httpx import AsyncClient, AsyncHTTPTransport

from .constants import (
    YOMA_FASTAPI_ENDPOINT,
    YOMA_ACAPY_API_KEY,
    MEMBER_FASTAPI_ENDPOINT,
    MEMBER_ACAPY_API_KEY,
)
from app.constants import YOMA_AGENT_URL, MEMBER_AGENT_URL

# YOMA


def yoma_client(*, app: Optional[Any] = None):
    return AsyncClient(
        base_url=YOMA_FASTAPI_ENDPOINT,
        timeout=60.0,
        app=app,
        headers={
            "x-api-key": f"yoma.{YOMA_ACAPY_API_KEY}",
            "content-type": "application/json",
        },
        transport=AsyncHTTPTransport(retries=3),
    )


def yoma_acapy_client():
    return AcaPyClient(
        base_url=YOMA_AGENT_URL,
        api_key=YOMA_ACAPY_API_KEY,
    )


# MEMBER ADMIN


def member_admin_client(*, app: Optional[Any] = None):
    return AsyncClient(
        base_url=MEMBER_FASTAPI_ENDPOINT,
        timeout=60.0,
        app=app,
        headers={
            "x-api-key": f"member-admin.{YOMA_ACAPY_API_KEY}",
            "content-type": "application/json",
        },
        transport=AsyncHTTPTransport(retries=3),
    )


def member_admin_acapy_client():
    return AcaPyClient(
        base_url=MEMBER_AGENT_URL,
        api_key=MEMBER_ACAPY_API_KEY,
    )


# MEMBER


def member_client(*, token: str, app: Optional[Any] = None):
    return AsyncClient(
        base_url=MEMBER_FASTAPI_ENDPOINT,
        timeout=60.0,
        app=app,
        headers={
            "x-api-key": f"member.{token}",
            "content-type": "application/json",
        },
    )


def member_acapy_client(*, token: str):
    return AcaPyClient(
        base_url=MEMBER_AGENT_URL, api_key=MEMBER_ACAPY_API_KEY, tenant_jwt=token
    )
