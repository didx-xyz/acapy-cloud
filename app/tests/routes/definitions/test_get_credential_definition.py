from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import CloudApiException
from app.models.definitions import CredentialDefinition
from app.routes.definitions import get_credential_definitions

cred_def_response = [
    CredentialDefinition(
        id="J5Pvam9KqK8ZPQWtvhAxSx:3:CL:8:Epic", tag="Epic", schema_id="8"
    ),
    CredentialDefinition(
        id="J5Pvam9KqK8ZPQWtvhAxSx:3:CL:9:Default", tag="Default", schema_id="9"
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params, response",
    [
        ({}, cred_def_response),
        ({"issuer_did": "J5Pvam9KqK8ZPQWtvhAxSx"}, cred_def_response),
        (
            {"credential_definition_id": "J5Pvam9KqK8ZPQWtvhAxSx:3:CL:8:Epic"},
            [cred_def_response[0]],
        ),
        ({"schema_id": "8"}, cred_def_response),
        ({"schema_issuer_did": "some_did"}, [cred_def_response[1]]),
        ({"schema_name": "some_name"}, [cred_def_response[1]]),
        ({"schema_version": "some_version"}, cred_def_response[0]),
        ({"credential_definition_id": "not_found_id"}, []),
    ],
)
async def test_get_credential_definitions_success(params, response) -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_get_client_controller,
        patch(
            "app.routes.definitions.cred_def_service.get_credential_definitions"
        ) as mock_get_credential_definitions,
    ):
        mock_get_credential_definitions.return_value = response
        mock_get_client_controller.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        cred_defs = await get_credential_definitions(
            auth="mocked_auth",
            **params,
        )

        mock_get_credential_definitions.assert_called_once_with(
            aries_controller=mock_aries_controller,
            issuer_did=params.get("issuer_did"),
            credential_definition_id=params.get("credential_definition_id"),
            schema_id=params.get("schema_id"),
            schema_issuer_did=params.get("schema_issuer_did"),
            schema_name=params.get("schema_name"),
            schema_version=params.get("schema_version"),
        )

        assert cred_defs == response


@pytest.mark.anyio
@pytest.mark.parametrize(
    "expected_status_code, expected_detail",
    [
        (400, "Bad request"),
        (500, "Internal Server Error"),
    ],
)
async def test_get_credential_definitions_fail_acapy_error(
    expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_get_client_controller,
        patch(
            "app.routes.definitions.cred_def_service.get_credential_definitions"
        ) as mock_get_credential_definitions,
    ):
        mock_get_credential_definitions.side_effect = CloudApiException(
            status_code=expected_status_code, detail=expected_detail
        )
        mock_get_client_controller.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        with pytest.raises(CloudApiException) as exc:
            await get_credential_definitions(auth="mocked_auth")

        assert exc.value.status_code == expected_status_code
        assert exc.value.detail == expected_detail
