from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import ApiException, BadRequestException
from aries_cloudcontroller.models import (
    CredentialDefinition,
    CredentialDefinitionGetResult,
)
from fastapi import HTTPException

from app.models.definitions import CredentialDefinition as CredentialDefinitionModel
from app.models.definitions import CredentialSchema
from app.routes.definitions import get_credential_definition_by_id

cred_def_id = "J5Pvam9KqK8ZPQWtvhAxSx:3:CL:8:Epic"
cred_def_acapy_result = CredentialDefinitionGetResult(
    credential_definition=CredentialDefinition(
        id=cred_def_id,
        tag="Epic",
        schema_id="8",
    )
)
schema = CredentialSchema(
    id="CxrsEqxTdGkiYq3rjByNkx:2:Epic_speed:1.0",
    name="Epic_speed",
    version="1.0",
    attribute_names=["speed"],
)
final_response = CredentialDefinitionModel(
    id=cred_def_id,
    tag="Epic",
    schema_id=schema.id,
)


@pytest.mark.anyio
async def test_get_credential_definition_by_id_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.credential_definition.get_cred_def = AsyncMock(
        return_value=cred_def_acapy_result
    )
    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_schema"
    ) as mock_get_schema, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_get_schema.return_value = schema
        get_response = await get_credential_definition_by_id(
            credential_definition_id=cred_def_id, auth="mocked_auth"
        )

        assert get_response == final_response

        mock_aries_controller.credential_definition.get_cred_def.assert_awaited_once_with(
            cred_def_id=cred_def_id,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_credential_definition_by_id_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.credential_definition.get_cred_def = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(HTTPException) as exc:
            await get_credential_definition_by_id(
                credential_definition_id=cred_def_id, auth="mocked_auth"
            )

        assert exc.value.status_code == expected_status_code
        assert exc.value.detail == expected_detail
        mock_aries_controller.credential_definition.get_cred_def.assert_awaited_once_with(
            cred_def_id=cred_def_id,
        )


@pytest.mark.anyio
async def test_get_credential_definition_by_id_404():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.credential_definition.get_cred_def = AsyncMock(
        return_value=None
    )

    with patch(
        "app.routes.definitions.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.definitions.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(HTTPException) as exc:
            await get_credential_definition_by_id(
                credential_definition_id=cred_def_id, auth="mocked_auth"
            )

        assert exc.value.status_code == 404
        mock_aries_controller.credential_definition.get_cred_def.assert_awaited_once_with(
            cred_def_id=cred_def_id,
        )
