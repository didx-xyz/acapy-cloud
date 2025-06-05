from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import CloudApiException
from app.models.definitions import CreateSchema, CredentialSchema
from app.routes.definitions import create_schema

create_anoncreds_schema_body = CreateSchema(
    schema_type="anoncreds",
    name="Test_AnonCreds_Schema_1",
    version="0.1.0",
    attribute_names=["attr1", "attr2"],
)
create_anoncreds_schema_response = CredentialSchema(
    id="27aG25kMFticzJ8GHH87BB:2:Test_AnonCreds_Schema_1:0.1.0",
    name="Test_AnonCreds_Schema_1",
    version="0.1.0",
    attribute_names=["attr1", "attr2"],
)


@pytest.mark.anyio
async def test_create_schema_success(mock_governance_auth):
    mock_aries_controller = AsyncMock()
    mock_create_schema_service = AsyncMock()

    request_body = create_anoncreds_schema_body
    create_schema_response = create_anoncreds_schema_response

    mock_create_schema_service.return_value = create_schema_response

    with (
        patch("app.routes.definitions.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.definitions.schemas_service.create_schema",
            mock_create_schema_service,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with patch(
            "app.routes.definitions.assert_public_did", return_value="public_did"
        ):
            response = await create_schema(
                schema=request_body, auth=mock_governance_auth
            )
            assert response == create_schema_response
            mock_create_schema_service.assert_called_once_with(
                aries_controller=mock_aries_controller,
                schema=request_body,
                public_did="public_did",
            )


@pytest.mark.anyio
async def test_create_schema_unauthorized_for_non_governance(
    mock_admin_auth, mock_tenant_auth_verified
):
    for auth in [mock_admin_auth, mock_tenant_auth_verified]:
        with pytest.raises(CloudApiException) as exc_info:
            await create_schema(schema=create_anoncreds_schema_body, auth=auth)
        assert exc_info.value.status_code == 403
        assert "Unauthorized" in str(exc_info.value)


@pytest.mark.anyio
async def test_create_schema_assert_public_did_failure(mock_governance_auth):
    mock_aries_controller = AsyncMock()
    mock_create_schema_service = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.definitions.schemas_service.create_schema",
            mock_create_schema_service,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        # Simulate assert_public_did raising a CloudApiException
        with patch(
            "app.routes.definitions.assert_public_did",
            side_effect=CloudApiException("No public DID", 404),
        ):
            with pytest.raises(CloudApiException) as exc_info:
                await create_schema(
                    schema=create_anoncreds_schema_body, auth=mock_governance_auth
                )
            assert exc_info.value.status_code == 500
            assert "Failed to fetch public DID for agent" in str(exc_info.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "expected_status_code, expected_detail",
    [
        (400, "Bad request"),
        (409, "Conflict"),
        (500, "Internal Server Error"),
    ],
)
async def test_create_schema_failure(
    mock_governance_auth, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_create_schema_service = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.definitions.schemas_service.create_schema",
            mock_create_schema_service,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        mock_create_schema_service.side_effect = CloudApiException(
            status_code=expected_status_code, detail=expected_detail
        )

        # Mock the assertion of public DID
        with patch(
            "app.routes.definitions.assert_public_did", return_value="public_did"
        ):
            with pytest.raises(CloudApiException, match=expected_detail):
                await create_schema(
                    schema=create_anoncreds_schema_body, auth=mock_governance_auth
                )

        mock_create_schema_service.assert_called_once_with(
            aries_controller=mock_aries_controller,
            schema=create_anoncreds_schema_body,
            public_did="public_did",
        )
