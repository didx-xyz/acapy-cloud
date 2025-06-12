from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.exceptions import CloudApiException
from app.models.issuer import ClearPendingRevocationsRequest
from app.routes.revocation import clear_pending_revocations

skip_reason = "Clear pending revocations is not yet implemented in AnonCreds"


@pytest.mark.anyio
@pytest.mark.skip(reason=skip_reason)
async def test_clear_pending_revocations_success() -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        patch(
            "app.services.revocation_registry.clear_pending_revocations"
        ) as mock_clear_pending_revocations,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        clear_request = ClearPendingRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await clear_pending_revocations(
            clear_pending_request=clear_request, auth="mocked_auth"
        )

        mock_clear_pending_revocations.assert_awaited_once_with(
            controller=mock_aries_controller, revocation_registry_credential_map={}
        )


@pytest.mark.anyio
@pytest.mark.skip(reason=skip_reason)
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_clear_pending_revocations_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.revocation.clear_pending_revocations = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        clear_request = ClearPendingRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await clear_pending_revocations(
            clear_pending_request=clear_request, auth="mocked_auth"
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
@pytest.mark.skip(reason=skip_reason)
async def test_clear_pending_revocations_fail_anoncreds_error() -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        pytest.raises(
            CloudApiException,
            match="Clearing pending revocations is not supported for the 'anoncreds' wallet type.",
        ) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        clear_request = ClearPendingRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await clear_pending_revocations(
            clear_pending_request=clear_request, auth="mocked_auth"
        )

    assert exc.value.status_code == 501
