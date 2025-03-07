from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import ApiException, BadRequestException
from aries_cloudcontroller.models.schema_get_result import ModelSchema, SchemaGetResult
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role",
    [
        "GOVERNANCE",
        "TENANT",
    ],
)
async def test_get_schema_by_id_success(role):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.schema.get_schema = AsyncMock(return_value=acapy_response)
    mock_aries_controller.server.get_config = AsyncMock(
        return_value={"wallet.type": "askar"}
    )
    mock_auth = AcaPyAuth(token="mocked_token", role=role)
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
        response = await get_schema(schema_id=schema_id, auth=mock_auth)

        assert response == schema_response

        mock_aries_controller.schema.get_schema.assert_awaited_once_with(
            schema_id=schema_id,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail, role",
    [
        (BadRequestException, 400, "Bad request", "GOVERNANCE"),
        (ApiException, 500, "Internal Server Error", "TENANT"),
    ],
)
async def test_get_schema_by_id_fail_acapy_error(
    exception_class, expected_status_code, expected_detail, role
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.schema.get_schema = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )
    mock_aries_controller.server.get_config = AsyncMock(
        return_value={"wallet.type": "askar"}
    )
    mock_auth = AcaPyAuth(token="mocked_token", role=role)
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
