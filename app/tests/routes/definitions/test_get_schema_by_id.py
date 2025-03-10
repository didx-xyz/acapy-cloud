from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    AdminConfig,
    AnonCredsSchema,
    ApiException,
    GetSchemaResult,
    ModelSchema,
    SchemaGetResult,
)
from aries_cloudcontroller.exceptions import BadRequestException
from fastapi import HTTPException

from app.dependencies.auth import AcaPyAuth
from app.dependencies.role import Role
from app.models.definitions import CredentialSchema
from app.routes.definitions import get_schema

schema_id = "27aG25kMFticzJ8GHH87BB:2:Test_Schema_1:0.1.0"
schema_response = CredentialSchema(
    id=schema_id,
    name="Test_Schema_1",
    version="0.1.0",
    attribute_names=["attr1", "attr2"],
)
acapy_response = SchemaGetResult(
    var_schema=ModelSchema(
        id=schema_id,
        name="Test_Schema_1",
        version="0.1.0",
        attr_names=["attr1", "attr2"],
    )
)
acapy_anoncreds_response = GetSchemaResult(
    schema_id=schema_id,
    var_schema=AnonCredsSchema(
        name="Test_Schema_1",
        version="0.1.0",
        attr_names=["attr1", "attr2"],
        issuer_id="27aG25kMFticzJ8GHH87BB",
    ),
)


@pytest.fixture
def setup_askar_wallet_type_mocks():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "askar"})
    )
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_wallet_type.return_value = "askar"
        yield mock_aries_controller


@pytest.mark.anyio
@pytest.mark.parametrize("role", [Role.GOVERNANCE, Role.TENANT])
async def test_get_schema_by_id_success(
    setup_askar_wallet_type_mocks, role  # pylint: disable=redefined-outer-name
):
    mock_aries_controller = setup_askar_wallet_type_mocks
    mock_aries_controller.schema.get_schema = AsyncMock(return_value=acapy_response)
    mock_auth = AcaPyAuth(token="mocked_token", role=role)

    response = await get_schema(schema_id=schema_id, auth=mock_auth)

    assert response == schema_response
    mock_aries_controller.schema.get_schema.assert_awaited_once_with(
        schema_id=schema_id,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail, role",
    [
        (BadRequestException, 400, "Bad request", Role.GOVERNANCE),
        (ApiException, 500, "Internal Server Error", Role.TENANT),
    ],
)
async def test_get_schema_by_id_fail_acapy_error(
    setup_askar_wallet_type_mocks,  # pylint: disable=redefined-outer-name
    exception_class,
    expected_status_code,
    expected_detail,
    role,
):
    mock_aries_controller = setup_askar_wallet_type_mocks
    mock_aries_controller.schema.get_schema = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )
    mock_auth = AcaPyAuth(token="mocked_token", role=role)

    with pytest.raises(HTTPException) as exc:
        await get_schema(schema_id=schema_id, auth=mock_auth)

    assert exc.value.status_code == expected_status_code
    assert exc.value.detail == expected_detail
    mock_aries_controller.schema.get_schema.assert_awaited_once_with(
        schema_id=schema_id,
    )


@pytest.mark.anyio
async def test_get_schema_by_id_404():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.schema.get_schema = AsyncMock(
        return_value=SchemaGetResult(var_schema=None)
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_wallet_type.return_value = "askar"

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth=mock_auth)

        assert exc.value.status_code == 404
        mock_aries_controller.schema.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
async def test_get_schema_by_id_askar_anoncreds():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=acapy_anoncreds_response
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_wallet_type.return_value = "askar-anoncreds"

        response = await get_schema(schema_id=schema_id, auth=mock_auth)

        assert response == schema_response

        mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
async def test_get_schema_by_id_var_schema_not_found():
    mock_aries_controller = AsyncMock()
    # Simulate a response where var_schema is None
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=GetSchemaResult(var_schema=None)
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_wallet_type.return_value = "askar-anoncreds"

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth=mock_auth)

        assert exc.value.status_code == 404
        assert exc.value.detail == f"Schema with id {schema_id} not found."

        mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
async def test_get_schema_by_id_unknown_wallet_type():
    mock_aries_controller = AsyncMock()
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_wallet_type.return_value = "unknown"

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth=mock_auth)

        assert exc.value.status_code == 500
        assert exc.value.detail == "Unknown wallet type"
