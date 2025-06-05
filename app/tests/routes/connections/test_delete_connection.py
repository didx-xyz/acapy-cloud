from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnRecord, Hangup
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import delete_connection_by_id

connection_id = "test_connection_id"


@pytest.mark.anyio
async def test_delete_connection_by_id_success():
    mock_aries_controller = AsyncMock()

    mock_aries_controller.connection.get_connection = AsyncMock(
        return_value=ConnRecord(
            connection_id=connection_id, connection_protocol="didexchange/1.1"
        )
    )
    mock_aries_controller.connection.delete_connection = AsyncMock()

    with patch("app.routes.connections.client_from_auth") as mock_client_from_auth:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await delete_connection_by_id(
            connection_id=connection_id, auth="mocked_auth"
        )

        assert response is None

        mock_aries_controller.connection.get_connection.assert_awaited_once_with(
            conn_id=connection_id,
        )
        mock_aries_controller.did_rotate.hangup.assert_awaited_once_with(
            conn_id=connection_id
        )


@pytest.mark.anyio
async def test_delete_connection_by_id_success_did_exchange():
    mock_aries_controller = AsyncMock()

    # Mock to return a connection that uses the didexchange protocol
    mock_aries_controller.connection.get_connection = AsyncMock(
        return_value=ConnRecord(
            connection_id=connection_id, connection_protocol="didexchange/1.1"
        )
    )
    mock_aries_controller.did_rotate.hangup = AsyncMock(return_value=Hangup())

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch("app.routes.connections.logger"),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await delete_connection_by_id(
            connection_id=connection_id, auth="mocked_auth"
        )

        assert response is None

        mock_aries_controller.connection.get_connection.assert_awaited_once_with(
            conn_id=connection_id
        )
        mock_aries_controller.did_rotate.hangup.assert_awaited_once_with(
            conn_id=connection_id
        )
        mock_aries_controller.connection.delete_connection.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_delete_connection_by_id_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.connection.delete_connection = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await delete_connection_by_id(connection_id=connection_id, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
