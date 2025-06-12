from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.dependencies.auth import (
    AcaPyAuth,
    AcaPyAuthVerified,
    acapy_auth_from_header,
    acapy_auth_governance,
    acapy_auth_tenant_admin,
    acapy_auth_verified,
    get_acapy_auth,
    get_acapy_auth_verified,
    tenant_api_key,
    verify_wallet_access,
)
from app.dependencies.role import Role
from shared.constants import (
    ACAPY_MULTITENANT_JWT_SECRET,
    GOVERNANCE_AGENT_API_KEY,
    GOVERNANCE_LABEL,
    TENANT_AGENT_API_KEY,
)


def test_acapy_auth_from_header() -> None:
    mock_api_key = MagicMock()
    with patch("app.dependencies.auth.get_acapy_auth") as mock_get_acapy_auth:
        acapy_auth_from_header(mock_api_key)
        mock_get_acapy_auth.assert_called_once_with(mock_api_key)


def test_get_acapy_auth_valid() -> None:
    api_key = "governance.gov-token"
    assert get_acapy_auth(api_key) == AcaPyAuth(role=Role.GOVERNANCE, token="gov-token")


def test_get_acapy_auth_invalid_format() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_acapy_auth("")
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        get_acapy_auth("no-period-in-api-key")
    assert exc_info.value.status_code == 401


def test_get_acapy_auth_unauthorized() -> None:
    with pytest.raises(HTTPException):
        get_acapy_auth("BadRole.token")


def test_get_acapy_auth_valid_tenant() -> None:
    assert get_acapy_auth("tenant.token") == AcaPyAuth(role=Role.TENANT, token="token")


def test_get_acapy_auth_valid_admin() -> None:
    assert get_acapy_auth("tenant-admin.token") == AcaPyAuth(
        role=Role.TENANT_ADMIN, token="token"
    )


def test_get_acapy_auth_valid_governance() -> None:
    assert get_acapy_auth("governance.token") == AcaPyAuth(
        role=Role.GOVERNANCE, token="token"
    )


def test_acapy_auth_verified_from_header() -> None:
    mock_auth = MagicMock()
    with patch(
        "app.dependencies.auth.get_acapy_auth_verified"
    ) as mock_get_acapy_auth_verified:
        acapy_auth_verified(mock_auth)
        mock_get_acapy_auth_verified.assert_called_once_with(mock_auth)


def test_get_acapy_auth_verified_valid_governance() -> None:
    auth = AcaPyAuth(role=Role.GOVERNANCE, token=GOVERNANCE_AGENT_API_KEY)
    assert get_acapy_auth_verified(auth) == AcaPyAuthVerified(
        role=Role.GOVERNANCE, token=GOVERNANCE_AGENT_API_KEY, wallet_id=GOVERNANCE_LABEL
    )


def test_get_acapy_auth_verified_governance_bad_token() -> None:
    auth = AcaPyAuth(role=Role.GOVERNANCE, token="bad-api-key")

    with pytest.raises(HTTPException) as exc:
        get_acapy_auth_verified(auth)
    assert exc.value.status_code == 403


def test_get_acapy_auth_verified_valid_admin() -> None:
    auth = AcaPyAuth(role=Role.TENANT_ADMIN, token=TENANT_AGENT_API_KEY)
    assert get_acapy_auth_verified(auth) == AcaPyAuthVerified(
        role=Role.TENANT_ADMIN, token=TENANT_AGENT_API_KEY, wallet_id="admin"
    )


def test_get_acapy_auth_verified_admin_bad_token() -> None:
    auth = AcaPyAuth(role=Role.TENANT_ADMIN, token="bad-api-key")

    with pytest.raises(HTTPException) as exc:
        get_acapy_auth_verified(auth)
    assert exc.value.status_code == 403


def test_get_acapy_auth_verified_valid_tenant() -> None:
    token_wallet_id = "366e25d3-3c71-491d-a339-4029120c7b2b"
    valid_payload = {"wallet_id": token_wallet_id}
    valid_tenant_jwt = jwt.encode(
        valid_payload, ACAPY_MULTITENANT_JWT_SECRET, algorithm="HS256"
    )
    auth = AcaPyAuth(role=Role.TENANT, token=valid_tenant_jwt)
    assert get_acapy_auth_verified(auth) == AcaPyAuthVerified(
        role=Role.TENANT, token=valid_tenant_jwt, wallet_id=token_wallet_id
    )


def test_get_acapy_auth_verified_tenant_bad_token() -> None:
    auth = AcaPyAuth(role=Role.TENANT, token="bad-api-key")

    with pytest.raises(HTTPException) as exc:
        get_acapy_auth_verified(auth)
    assert exc.value.status_code == 403


def test_get_acapy_auth_verified_tenant_valid_token_no_wallet_id() -> None:
    invalid_payload = {"bad_key": "123"}
    bad_tenant_jwt = jwt.encode(
        invalid_payload, ACAPY_MULTITENANT_JWT_SECRET, algorithm="HS256"
    )
    auth = AcaPyAuth(role=Role.TENANT, token=bad_tenant_jwt)

    with pytest.raises(HTTPException) as exc:
        get_acapy_auth_verified(auth)
    assert exc.value.status_code == 403


def test_acapy_auth_governance_success() -> None:
    auth = AcaPyAuth(role=Role.GOVERNANCE, token="gov-api-key")
    assert acapy_auth_governance(auth) == AcaPyAuthVerified(
        role=Role.GOVERNANCE, token="gov-api-key", wallet_id=GOVERNANCE_LABEL
    )


def test_acapy_auth_governance_wrong_role() -> None:
    with pytest.raises(HTTPException) as exc_info:
        acapy_auth_governance(AcaPyAuth(role=Role.TENANT_ADMIN, token="admin-api-key"))
    assert exc_info.value.status_code == 403


def test_acapy_auth_tenant_admin_success() -> None:
    auth = AcaPyAuth(role=Role.TENANT_ADMIN, token="admin-api-key")
    assert acapy_auth_tenant_admin(auth) == AcaPyAuthVerified(
        role=Role.TENANT_ADMIN, token="admin-api-key", wallet_id="admin"
    )


def test_acapy_auth_tenant_admin_failure() -> None:
    with pytest.raises(HTTPException) as exc_info:
        acapy_auth_tenant_admin(AcaPyAuth(role=Role.TENANT, token="tenant-api-key"))
    assert exc_info.value.status_code == 403


def test_verify_wallet_access_admin() -> None:
    auth_verified = AcaPyAuthVerified(
        role=Role.TENANT_ADMIN, token="tenant-admin-token", wallet_id="admin"
    )
    # Admin can access "admin" wallet and other wallets
    verify_wallet_access(auth_verified, "admin")
    verify_wallet_access(auth_verified, "any_wallet")


def test_verify_wallet_access_tenant() -> None:
    auth_verified = AcaPyAuthVerified(
        role=Role.TENANT, token="tenant-token", wallet_id="some_wallet"
    )
    # Cannot access "admin" wallet
    with pytest.raises(HTTPException) as exc_info:
        verify_wallet_access(auth_verified, "admin")
    assert exc_info.value.status_code == 403

    # Cannot access other wallets
    with pytest.raises(HTTPException) as exc_info:
        verify_wallet_access(auth_verified, "other_wallet")
    assert exc_info.value.status_code == 403

    # Can access own wallet
    verify_wallet_access(auth_verified, "some_wallet")


def test_tenant_api_key() -> None:
    tenant_token = "tenant-jwt"
    assert tenant_api_key(tenant_token) == "tenant.tenant-jwt"
