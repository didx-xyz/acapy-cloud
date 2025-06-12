from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.issuer import RevokeCredential
from app.routes.revocation import revoke_credential

credential_exchange_id = "v2-db9d7025-b276-4c32-ae38-fbad41864112"


@pytest.mark.anyio
@pytest.mark.parametrize("auto_publish_to_ledger", [True, False])
async def test_revoke_credential_success(auto_publish_to_ledger) -> None:
    mock_aries_controller = AsyncMock()
    mock_revoke_credential = AsyncMock()
    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        patch(
            "app.services.revocation_registry.revoke_credential", mock_revoke_credential
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        request_body = RevokeCredential(
            credential_exchange_id=credential_exchange_id,
            auto_publish_on_ledger=auto_publish_to_ledger,
        )

        await revoke_credential(body=request_body, auth="mocked_auth")

        mock_revoke_credential.assert_awaited_once_with(
            controller=mock_aries_controller,
            credential_exchange_id=credential_exchange_id,
            auto_publish_to_ledger=auto_publish_to_ledger,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (CloudApiException, 400, "Bad request"),
        (CloudApiException, 404, "Not found"),
        (CloudApiException, 500, "Internal Server Error"),
    ],
)
async def test_revoke_credential_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_revoke_credential = AsyncMock(
        side_effect=exception_class(
            status_code=expected_status_code, detail=expected_detail
        )
    )

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        pytest.raises(CloudApiException, match=expected_detail) as exc,
        patch(
            "app.services.revocation_registry.revoke_credential", mock_revoke_credential
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        request_body = RevokeCredential(
            credential_exchange_id=credential_exchange_id,
            auto_publish_on_ledger=False,
        )

        await revoke_credential(body=request_body, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
