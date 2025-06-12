from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import CloudApiException
from app.models.definitions import CreateCredentialDefinition, CredentialDefinition
from app.routes.definitions import create_credential_definition

create_cred_def_body = CreateCredentialDefinition(
    schema_id="mock_schema_id",
    tag="mock_tag",
    support_revocation=False,
)
cred_def_response = CredentialDefinition(
    id="mock_credential_definition_id",
    schema_id="mock_schema_id",
    tag="mock_tag",
)


@pytest.mark.anyio
async def test_create_credential_definition_success() -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_get_client_controller,
        patch(
            "app.routes.definitions.cred_def_service.create_credential_definition"
        ) as mock_create_credential_definition,
        patch(
            "app.routes.definitions.coroutine_with_retry"
        ) as mock_coroutine_with_retry,
    ):
        mock_get_client_controller.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_coroutine_with_retry.return_value = cred_def_response

        response = await create_credential_definition(
            auth="mocked_auth",
            credential_definition=create_cred_def_body,
        )

        mock_create_credential_definition.assert_called_once_with(
            aries_controller=mock_aries_controller,
            credential_definition=create_cred_def_body,
            support_revocation=False,
        )

        mock_coroutine_with_retry.assert_awaited()

        assert response == cred_def_response


@pytest.mark.anyio
@pytest.mark.parametrize(
    "expected_status_code, expected_detail",
    [
        (400, "Bad request"),
        (409, "Conflict"),
        (500, "Internal Server Error"),
    ],
)
async def test_create_credential_definition_fail_acapy_error(
    expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.definitions.client_from_auth") as mock_get_client_controller,
        patch(
            "app.routes.definitions.cred_def_service.create_credential_definition"
        ) as mock_create_credential_definition,
    ):
        mock_get_client_controller.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_create_credential_definition.side_effect = CloudApiException(
            status_code=expected_status_code, detail=expected_detail
        )

        with pytest.raises(CloudApiException) as exc:
            await create_credential_definition(
                auth="mocked_auth",
                credential_definition=create_cred_def_body,
            )

        assert exc.value.status_code == expected_status_code
        assert exc.value.detail == expected_detail
