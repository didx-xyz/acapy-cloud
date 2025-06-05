from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnRecord
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import accept_did_exchange_request

test_their_public_did = "did:sov:12345"
created_connection = ConnRecord(
    connection_id="some_connection_id",
    state="request-sent",
    their_did=test_their_public_did,
)


@pytest.mark.anyio
async def test_accept_did_exchange_request_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.accept_request = AsyncMock(
        return_value=created_connection
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=created_connection,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await accept_did_exchange_request(
            connection_id="some_connection_id",
            auth="mocked_auth",
        )

        assert response == created_connection

        mock_aries_controller.did_exchange.accept_request.assert_awaited_once_with(
            conn_id="some_connection_id",
            use_public_did=False,
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
async def test_accept_did_exchange_request_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.accept_request = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
        patch("app.routes.connections.conn_record_to_connection"),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await accept_did_exchange_request(
            connection_id="some_connection_id",
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code
