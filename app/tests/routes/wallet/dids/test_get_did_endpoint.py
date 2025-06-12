from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import DIDEndpoint
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.wallet.dids import get_did_endpoint

did = "did:cheqd:2cpBmR3FqGKWi5EyUbpRY8"


@pytest.mark.anyio
async def test_get_did_endpoint_success() -> None:
    expected_response = DIDEndpoint(did=did, endpoint="https://example.com")
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.get_did_endpoint = AsyncMock(
        return_value=expected_response
    )

    with patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await get_did_endpoint(did=did, auth="mocked_auth")

        assert response == expected_response
        mock_aries_controller.wallet.get_did_endpoint.assert_awaited_once_with(did=did)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_did_endpoint_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.get_did_endpoint = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_did_endpoint(did=did, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
