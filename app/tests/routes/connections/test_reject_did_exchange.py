from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnRecord
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import reject_did_exchange

test_their_public_did = "did:cheqd:12345"
created_connection = ConnRecord(
    connection_id="some_connection_id",
    state="request-sent",
    their_did=test_their_public_did,
)


@pytest.mark.anyio
async def test_reject_did_exchange_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.reject = AsyncMock(
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

        response = await reject_did_exchange(
            connection_id="some_connection_id",
            body=None,
            auth="mocked_auth",
        )

        assert response == created_connection

        mock_aries_controller.did_exchange.reject.assert_awaited_once_with(
            conn_id="some_connection_id",
            body=None,
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
async def test_reject_did_exchange_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.reject = AsyncMock(
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

        await reject_did_exchange(
            connection_id="some_connection_id",
            body=None,
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code
