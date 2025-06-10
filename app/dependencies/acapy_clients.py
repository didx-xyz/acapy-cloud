from aries_cloudcontroller import AcaPyClient
from fastapi import HTTPException

from app.dependencies.auth import AcaPyAuth, AcaPyAuthVerified
from app.dependencies.role import Role
from shared.constants import GOVERNANCE_LABEL

GOVERNANCE_AUTHED = AcaPyAuthVerified(
    role=Role.GOVERNANCE,
    token=Role.GOVERNANCE.agent_type.x_api_key,
    wallet_id=GOVERNANCE_LABEL,
)
TENANT_ADMIN_AUTHED = AcaPyAuthVerified(
    role=Role.TENANT_ADMIN,
    token=Role.TENANT_ADMIN.agent_type.x_api_key,
    wallet_id="admin",
)


def get_governance_controller(
    auth: AcaPyAuthVerified = GOVERNANCE_AUTHED,
) -> AcaPyClient:
    return AcaPyClient(
        base_url=Role.GOVERNANCE.agent_type.base_url,
        api_key=auth.token,
    )


def get_tenant_admin_controller(
    auth: AcaPyAuthVerified = TENANT_ADMIN_AUTHED,
) -> AcaPyClient:
    return AcaPyClient(
        base_url=Role.TENANT_ADMIN.agent_type.base_url,
        api_key=auth.token,
    )


def get_tenant_controller(auth_token: str) -> AcaPyClient:
    return AcaPyClient(
        base_url=Role.TENANT.agent_type.base_url,
        api_key=Role.TENANT.agent_type.x_api_key,
        tenant_jwt=auth_token,
    )


def client_from_auth(auth: AcaPyAuth | AcaPyAuthVerified) -> AcaPyClient:
    if not auth or not auth.token:
        raise HTTPException(403, "Missing authorization key.")

    tenant_jwt = None

    if auth.role.is_multitenant and not auth.role.is_admin:
        tenant_jwt = auth.token
        x_api_key = auth.role.agent_type.x_api_key
    else:
        x_api_key = auth.token

    client = AcaPyClient(
        base_url=auth.role.agent_type.base_url,
        api_key=x_api_key,
        tenant_jwt=tenant_jwt,
    )
    return client
