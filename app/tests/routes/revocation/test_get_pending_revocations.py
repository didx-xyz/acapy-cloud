from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.revocation import get_pending_revocations

rev_reg_id = "mocked_rev_reg_id"


@pytest.mark.anyio
async def test_get_pending_revocations_success():
    mock_aries_controller = AsyncMock()
    mock_get_pending_revocations = AsyncMock(return_value=[1, 2, 3])

    with patch(
        "app.routes.revocation.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.services.revocation_registry.get_pending_revocations",
        mock_get_pending_revocations,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_pending_revocations(
            auth="mocked_auth", revocation_registry_id=rev_reg_id
        )

        mock_get_pending_revocations.assert_awaited_once_with(
            controller=mock_aries_controller, rev_reg_id=rev_reg_id
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_pending_revocations_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.revocation.get_registry = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.revocation.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException,
        match=expected_detail,
    ) as exc, patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_pending_revocations(
            auth="mocked_auth", revocation_registry_id=rev_reg_id
        )

    assert exc.value.status_code == expected_status_code
