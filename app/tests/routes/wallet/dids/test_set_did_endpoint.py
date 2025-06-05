from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import DIDEndpointWithType
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.models.wallet import SetDidEndpointRequest
from app.routes.wallet.dids import set_did_endpoint

did = "did:sov:2cpBmR3FqGKWi5EyUbpRY8"


@pytest.mark.anyio
async def test_set_did_endpoint_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.set_did_endpoint = AsyncMock()

    request_body = SetDidEndpointRequest(endpoint="https://example.com")
    endpoint_type = "Endpoint"

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.wallet.dids.handle_model_with_validation",
            return_value=DIDEndpointWithType(
                did=did, endpoint=request_body.endpoint, endpoint_type=endpoint_type
            ),
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await set_did_endpoint(did=did, body=request_body, auth="mocked_auth")

        mock_aries_controller.wallet.set_did_endpoint.assert_awaited_once_with(
            body=DIDEndpointWithType(
                did=did, endpoint=request_body.endpoint, endpoint_type=endpoint_type
            ),
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
async def test_set_did_endpoint_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.set_did_endpoint = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        request_body = SetDidEndpointRequest(endpoint="https://example.com")

        await set_did_endpoint(did=did, body=request_body, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
