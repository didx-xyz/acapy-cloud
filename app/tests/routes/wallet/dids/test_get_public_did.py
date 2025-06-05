from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import DID, DIDResult
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.wallet.dids import get_public_did

sample_did = DID(
    did="2cpBmR3FqGKWi5EyUbpRY8",
    key_type="ed25519",
    method="sov",
    posture="posted",
    verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
)


@pytest.mark.anyio
@pytest.mark.parametrize("expected_result", [DIDResult(), DIDResult(result=sample_did)])
async def test_get_public_did_success(expected_result):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.get_public_did = AsyncMock(
        return_value=expected_result
    )

    with patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if not expected_result.result:
            # We expect a 404 when DID is not found
            with pytest.raises(HTTPException, match="No public did found.") as exc:
                await get_public_did(auth="mocked_auth")
                assert exc.status_code == 404
        else:
            assert await get_public_did(auth="mocked_auth") == sample_did
            mock_aries_controller.wallet.get_public_did.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_public_did_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.get_public_did = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_public_did(auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
