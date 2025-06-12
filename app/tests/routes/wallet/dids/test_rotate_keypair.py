from unittest.mock import AsyncMock, Mock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.wallet.dids import rotate_keypair

did = "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6"


@pytest.mark.anyio
async def test_rotate_keypair_success() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.rotate_keypair = AsyncMock(return_value=Mock())

    with patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await rotate_keypair(did=did, auth="mocked_auth")

        mock_aries_controller.wallet.rotate_keypair.assert_awaited_once_with(did=did)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_rotate_keypair_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.rotate_keypair = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await rotate_keypair(did="did:cheqd:12345", auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
