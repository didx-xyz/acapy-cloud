from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import CloudApiException
from app.models.definitions import CreateSchema, CredentialSchema
from app.routes.definitions import create_schema

create_indy_schema_body = CreateSchema(
    schema_type="indy",
    name="Test_Indy_Schema_1",
    version="0.1.0",
    attribute_names=["attr1", "attr2"],
)

create_anoncreds_schema_body = CreateSchema(
    schema_type="anoncreds",
    name="Test_AnonCreds_Schema_1",
    version="0.1.0",
    attribute_names=["attr1", "attr2"],
)
create_indy_schema_response = CredentialSchema(
    id="27aG25kMFticzJ8GHH87BB:2:Test_Indy_Schema_1:0.1.0",
    name="Test_Indy_Schema_1",
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
@pytest.mark.parametrize(
    "request_body", [create_anoncreds_schema_body, create_indy_schema_body]
)
async def test_create_schema_success(
    mock_tenant_auth_verified, mock_governance_auth, request_body
):
    mock_aries_controller = AsyncMock()
    mock_create_schema_service = AsyncMock()

    if request_body == create_anoncreds_schema_body:
        schema_type = "anoncreds"
        create_schema_response = create_anoncreds_schema_response
    else:
        schema_type = "indy"
        create_schema_response = create_indy_schema_response

    mock_create_schema_service.return_value = create_schema_response

    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.schemas_service.create_schema",
        mock_create_schema_service,
    ), patch(
        "app.routes.definitions.assert_valid_issuer", AsyncMock()
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        # Mock the assertion of public DID and wallet type
        if schema_type == "anoncreds":
            public_did = "public_did"
            # Assert wallet_type checks
            for wallet_type in ["askar-anoncreds", "askar"]:
                with patch(
                    "app.util.valid_issuer.assert_issuer_public_did",
                    return_value=public_did,
                ), patch(
                    "app.util.valid_issuer.get_wallet_type",
                    return_value=wallet_type,
                ):
                    if wallet_type == "askar-anoncreds":
                        # Succeeds with anoncreds wallet type
                        response = await create_schema(
                            schema=request_body, auth=mock_tenant_auth_verified
                        )
                        assert response == create_schema_response
                        mock_create_schema_service.assert_called_once_with(
                            aries_controller=mock_aries_controller,
                            schema=request_body,
                            public_did=public_did,
                        )
                    else:
                        # Fails with askar wallet type
                        with pytest.raises(
                            CloudApiException,
                            match="Only valid AnonCreds issuers can create AnonCreds schemas",
                        ) as exc:
                            await create_schema(
                                schema=request_body, auth=mock_tenant_auth_verified
                            )
                        assert exc.value.status_code == 403
        else:
            # Indy request fails with tenant auth
            with pytest.raises(CloudApiException, match="Unauthorized") as exc:
                await create_schema(schema=request_body, auth=mock_tenant_auth_verified)
            assert exc.value.status_code == 403

            # Succeeds with governance auth
            response = await create_schema(
                schema=request_body, auth=mock_governance_auth
            )
            assert response == create_schema_response

            mock_create_schema_service.assert_called_once_with(
                aries_controller=mock_aries_controller,
                schema=request_body,
                public_did=None,
            )


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
    mock_tenant_auth, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_create_schema_service = AsyncMock()

    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.schemas_service.create_schema",
        mock_create_schema_service,
    ), patch(
        "app.routes.definitions.assert_valid_issuer",
        AsyncMock(),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        mock_create_schema_service.side_effect = CloudApiException(
            status_code=expected_status_code, detail=expected_detail
        )

        # Mock the assertion of public DID and wallet type
        with patch(
            "app.routes.definitions.assert_public_did_and_wallet_type",
            return_value=("public_did", "askar-anoncreds"),
        ):
            with pytest.raises(CloudApiException, match=expected_detail):
                await create_schema(
                    schema=create_anoncreds_schema_body, auth=mock_tenant_auth
                )

        mock_create_schema_service.assert_called_once_with(
            aries_controller=mock_aries_controller,
            schema=create_anoncreds_schema_body,
            public_did="public_did",
        )
