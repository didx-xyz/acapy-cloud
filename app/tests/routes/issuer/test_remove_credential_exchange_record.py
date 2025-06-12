from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.issuer import remove_credential_exchange_record


@pytest.mark.anyio
async def test_remove_credential_exchange_record_success() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.delete_record = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await remove_credential_exchange_record(
            credential_exchange_id="v2-test_id", auth="mocked_auth"
        )

        mock_aries_controller.issue_credential_v2_0.delete_record.assert_awaited_once_with(
            cred_ex_id="test_id"
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
async def test_remove_credential_exchange_record_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.delete_record = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.issuer.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await remove_credential_exchange_record(
            credential_exchange_id="v2-test_id", auth="mocked_auth"
        )

    assert exc.value.status_code == expected_status_code
