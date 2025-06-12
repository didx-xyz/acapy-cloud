from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import get_connection_by_id
from shared.models.connection_record import Connection

connection_id = "test_connection_id"
connection_response = Connection(
    connection_id=connection_id,
    state="completed",
    alias="Test Alias",
)


@pytest.mark.anyio
async def test_get_connection_by_id_success() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.connection.get_connection = AsyncMock(
        return_value=connection_response
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=connection_response,
        ),
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await get_connection_by_id(
            connection_id=connection_id, auth="mocked_auth"
        )

        assert response == connection_response

        mock_aries_controller.connection.get_connection.assert_awaited_once_with(
            conn_id=connection_id,
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
async def test_get_connection_by_id_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.connection.get_connection = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
        patch("app.routes.connections.conn_record_to_connection"),
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_connection_by_id(connection_id=connection_id, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
