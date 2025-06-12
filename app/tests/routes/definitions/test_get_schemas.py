from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies.auth import AcaPyAuth
from app.dependencies.role import Role
from app.exceptions import CloudApiException
from app.models.definitions import CredentialSchema
from app.routes.definitions import get_schemas

schema_response = [
    CredentialSchema(
        id="27aG25kMFticzJ8GHH87BB:2:Test_Schema_1:0.1.0",
        name="Test_Schema_1",
        version="0.1.0",
        attribute_names=["attr1", "attr2"],
    ),
    CredentialSchema(
        id="27aG25kMFticzJ8GHH87BB:2:Test_Schema_2:0.1.0",
        name="Test_Schema_2",
        version="0.1.0",
        attribute_names=["attr3", "attr4"],
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params, response, role",
    [
        ({}, schema_response, Role.GOVERNANCE),
        ({}, [], Role.TENANT),
        (
            {"schema_name": "Test_Schema_1"},
            [schema_response[0]],
            Role.TENANT,
        ),
        ({"schema_name": "Test_Schema_2"}, [schema_response[1]], Role.GOVERNANCE),
        ({"schema_version": "0.1.0"}, schema_response, Role.TENANT),
        (
            {"schema_issuer_did": "27aG25kMFticzJ8GHH87BB"},
            schema_response,
            Role.GOVERNANCE,
        ),
        (
            {
                "schema_name": "Test_Schema_1",
                "schema_version": "0.1.0",
            },
            [schema_response[0]],
            Role.TENANT,
        ),
    ],
)
async def test_get_schemas_success(params, response, role) -> None:
    mock_aries_controller = AsyncMock()
    mock_auth = AcaPyAuth(token="mocked_token", role=role)

    with (
        patch("app.routes.definitions.client_from_auth") as mock_acapy_auth,
        patch(
            "app.routes.definitions.schemas_service.get_schemas_as_tenant"
        ) as mock_get_schemas_as_tenant,
        patch(
            "app.routes.definitions.schemas_service.get_schemas_as_governance"
        ) as mock_get_schemas_as_governance,
    ):
        mock_acapy_auth.return_value.__aenter__.return_value = mock_aries_controller
        mock_get_schemas_as_tenant.return_value = response
        mock_get_schemas_as_governance.return_value = response

        get_response = await get_schemas(auth=mock_auth, **params)

        if role == Role.TENANT:
            mock_get_schemas_as_tenant.assert_called_once_with(
                aries_controller=mock_aries_controller,
                schema_issuer_did=params.get("schema_issuer_did"),
                schema_name=params.get("schema_name"),
                schema_version=params.get("schema_version"),
            )
        else:
            mock_get_schemas_as_governance.assert_called_once_with(
                aries_controller=mock_aries_controller,
                schema_issuer_did=params.get("schema_issuer_did"),
                schema_name=params.get("schema_name"),
                schema_version=params.get("schema_version"),
            )
        assert get_response == response


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error_code, detail, role",
    [
        (400, "Bad request", Role.GOVERNANCE),
        (500, "Internal Server Error", Role.GOVERNANCE),
    ],
)
async def test_get_schemas_failure(error_code, detail, role) -> None:
    mock_aries_controller = AsyncMock()
    mock_auth = AcaPyAuth(token="mocked_token", role=role)

    with (
        patch("app.routes.definitions.client_from_auth") as mock_acapy_auth,
        patch(
            "app.routes.definitions.schemas_service.get_schemas_as_tenant"
        ) as mock_get_schemas_as_tenant,
        patch(
            "app.routes.definitions.schemas_service.get_schemas_as_governance"
        ) as mock_get_schemas_as_governance,
    ):
        mock_get_schemas_as_tenant.side_effect = CloudApiException(
            status_code=error_code, detail=detail
        )
        mock_get_schemas_as_governance.side_effect = CloudApiException(
            status_code=error_code, detail=detail
        )

        mock_acapy_auth.return_value.__aenter__.return_value = mock_aries_controller

        with pytest.raises(CloudApiException) as exc:
            await get_schemas(auth=mock_auth)

        assert exc.value.detail == detail
        assert exc.value.status_code == error_code
