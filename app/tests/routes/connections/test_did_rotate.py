from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import DIDRotateRequestJSON, Rotate
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import rotate_did


@pytest.mark.anyio
async def test_rotate_did_success():
    rotate_response = Rotate(to_did="did:cheqd:12345")
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_rotate.rotate = AsyncMock(return_value=rotate_response)

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch("app.routes.connections.logger"),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await rotate_did(
            connection_id="some_connection_id",
            to_did="did:cheqd:12345",
            auth="mocked_auth",
        )

        assert response == rotate_response

        mock_aries_controller.did_rotate.rotate.assert_awaited_once_with(
            conn_id="some_connection_id",
            body=DIDRotateRequestJSON(to_did="did:cheqd:12345"),
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
async def test_rotate_did_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_rotate.rotate = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await rotate_did(
            connection_id="some_connection_id",
            to_did="did:cheqd:12345",
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code
