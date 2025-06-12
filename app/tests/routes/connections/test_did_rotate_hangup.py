from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import Hangup
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import hangup_did_rotation


@pytest.mark.anyio
async def test_hangup_did_rotation_success():
    hangup_response = Hangup()
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_rotate.hangup = AsyncMock(return_value=hangup_response)

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch("app.routes.connections.logger"),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await hangup_did_rotation(
            connection_id="some_connection_id",
            auth="mocked_auth",
        )

        assert response == hangup_response

        mock_aries_controller.did_rotate.hangup.assert_awaited_once_with(
            conn_id="some_connection_id",
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
async def test_hangup_did_rotation_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_rotate.hangup = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await hangup_did_rotation(
            connection_id="some_connection_id",
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code
