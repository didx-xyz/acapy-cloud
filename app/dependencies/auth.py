from dataclasses import dataclass

import jwt
from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.security import APIKeyHeader

from app.dependencies.role import Role
from shared.constants import ACAPY_MULTITENANT_JWT_SECRET, GOVERNANCE_LABEL

x_api_key_scheme = APIKeyHeader(name="x-api-key")


@dataclass
class AcaPyAuth:
    token: str
    role: Role


@dataclass
class AcaPyAuthVerified(AcaPyAuth):
    wallet_id: str


def acapy_auth_from_header(api_key: str = Depends(x_api_key_scheme)) -> AcaPyAuth:  # type: ignore
    return get_acapy_auth(api_key)


def get_acapy_auth(api_key: str) -> AcaPyAuth:
    if "." not in api_key:
        raise HTTPException(401, "Unauthorized")

    [role_str, token] = api_key.split(".", maxsplit=1)

    role = Role.from_str(role_str)

    if not role:
        raise HTTPException(401, "Unauthorized")

    return AcaPyAuth(role=role, token=token)


def acapy_auth_verified(
    auth: AcaPyAuth = Depends(acapy_auth_from_header),  # type: ignore
) -> AcaPyAuthVerified:
    return get_acapy_auth_verified(auth)


def get_acapy_auth_verified(auth: AcaPyAuth) -> AcaPyAuthVerified:
    if auth.role.is_admin:
        if auth.token != auth.role.agent_type.x_api_key:
            raise HTTPException(403, "Unauthorized") from None

        wallet_id = GOVERNANCE_LABEL if auth.role == Role.GOVERNANCE else "admin"
    else:
        try:
            # Decode JWT
            token_body = jwt.decode(
                auth.token, ACAPY_MULTITENANT_JWT_SECRET, algorithms=["HS256"], leeway=1
            )
        except jwt.InvalidTokenError:
            raise HTTPException(403, "Unauthorized") from None

        wallet_id = token_body.get("wallet_id")

        if not wallet_id:
            raise HTTPException(403, "Unauthorized") from None

    return AcaPyAuthVerified(role=auth.role, token=auth.token, wallet_id=wallet_id)


def acapy_auth_governance(
    auth: AcaPyAuth = Depends(acapy_auth_from_header),  # type: ignore
) -> AcaPyAuthVerified:
    if auth.role == Role.GOVERNANCE:
        return AcaPyAuthVerified(
            role=auth.role, token=auth.token, wallet_id=GOVERNANCE_LABEL
        )
    else:
        raise HTTPException(403, "Unauthorized")


def acapy_auth_tenant_admin(
    auth: AcaPyAuth = Depends(acapy_auth_from_header),  # type: ignore
) -> AcaPyAuthVerified:
    if auth.role == Role.TENANT_ADMIN:
        return AcaPyAuthVerified(role=auth.role, token=auth.token, wallet_id="admin")
    else:
        raise HTTPException(403, "Unauthorized")


def verify_wallet_access(auth: AcaPyAuthVerified, wallet_id: str) -> None:
    if auth.wallet_id not in ("admin", wallet_id):
        raise HTTPException(403, "Unauthorized")


def tenant_api_key(tenant_token: str) -> str:
    """Get the cloud api key for a tenant with specified role."""
    return f"tenant.{tenant_token}"
