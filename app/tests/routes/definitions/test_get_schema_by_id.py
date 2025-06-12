from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    AnonCredsSchema,
    ApiException,
    GetSchemaResult,
    ModelSchema,
    SchemaGetResult,
)
from aries_cloudcontroller.exceptions import BadRequestException
from fastapi import HTTPException

from app.dependencies.auth import AcaPyAuth
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


@pytest.mark.anyio
async def test_get_schema_by_id_success() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=acapy_anoncreds_response
    )
    with patch("app.routes.definitions.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await get_schema(schema_id=schema_id, auth="mock_auth")

    assert response == schema_response
    mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
        schema_id=schema_id,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_schema_by_id_fail_acapy_error(
    exception_class,
    expected_status_code,
    expected_detail,
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )
    with patch("app.routes.definitions.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth="mock_auth")

    assert exc.value.status_code == expected_status_code
    assert exc.value.detail == expected_detail
    mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
        schema_id=schema_id,
    )


@pytest.mark.anyio
async def test_get_schema_by_id_404() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=SchemaGetResult(var_schema=None)
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch("app.routes.definitions.client_from_auth") as mock_client_from_auth:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth=mock_auth)

        assert exc.value.status_code == 404
        mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
async def test_get_schema_by_id_askar_anoncreds() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=acapy_anoncreds_response
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch("app.routes.definitions.client_from_auth") as mock_client_from_auth:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await get_schema(schema_id=schema_id, auth=mock_auth)

        assert response == schema_response

        mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
async def test_get_schema_by_id_var_schema_not_found() -> None:
    mock_aries_controller = AsyncMock()
    # Simulate a response where var_schema is None
    mock_aries_controller.anoncreds_schemas.get_schema = AsyncMock(
        return_value=GetSchemaResult(var_schema=None)
    )
    mock_auth = AcaPyAuth(token="mocked_token", role="TENANT")
    with patch("app.routes.definitions.client_from_auth") as mock_client_from_auth:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(HTTPException) as exc:
            await get_schema(schema_id=schema_id, auth=mock_auth)

        assert exc.value.status_code == 404
        assert exc.value.detail == f"Schema with id {schema_id} not found."

        mock_aries_controller.anoncreds_schemas.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )
