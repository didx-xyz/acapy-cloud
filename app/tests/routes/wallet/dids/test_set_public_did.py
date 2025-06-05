from unittest.mock import AsyncMock, Mock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)

from app.routes.wallet.dids import set_public_did

did = "did:sov:2cpBmR3FqGKWi5EyUbpRY8"


@pytest.mark.anyio
async def test_set_public_did_success():
    mock_aries_controller = AsyncMock()
    mock_set_public_did = AsyncMock(return_value=Mock())

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        patch("app.services.acapy_wallet.set_public_did", mock_set_public_did),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await set_public_did(did=did, auth="mocked_auth")

        mock_set_public_did.assert_awaited_once_with(mock_aries_controller, did)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_set_public_did_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_set_public_did = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(exception_class, match=expected_detail) as exc,
        patch("app.services.acapy_wallet.set_public_did", mock_set_public_did),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await set_public_did(did="did:sov:12345", auth="mocked_auth")

    assert exc.value.status == expected_status_code
