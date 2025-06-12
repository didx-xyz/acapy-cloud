from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnectionList, ConnRecord
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import get_connections

connections_response = ConnectionList(
    results=[
        ConnRecord(connection_id="conn1", state="active"),
        ConnRecord(connection_id="conn2", state="completed"),
    ]
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"alias": "test_alias"},
        {"connection_protocol": "didexchange/1.1"},
        {"invitation_key": "invitation_key"},
        {"invitation_msg_id": "invitation_msg_id"},
        {"their_role": "invitee"},
        {"alias": "test_alias", "state": "active"},
        {"state": "active"},
        {"my_did": "my_did"},
        {"their_did": "their_did"},
        {"alias": "test_alias", "their_public_did": "their_public_did", "limit": 10},
        {"limit": 5, "offset": 5},
        {"descending": False},
        {"descending": True},
    ],
)
async def test_get_connections_success(params) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=connections_response
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection", side_effect=lambda x: x
        ),
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        # to fix Query objects not being comparable to expected
        if "limit" not in params:
            params["limit"] = 100
        if "offset" not in params:
            params["offset"] = 0
        if "descending" not in params:
            params["descending"] = True
        if "order_by" not in params:
            params["order_by"] = "id"

        response = await get_connections(auth="mocked_auth", **params)

        assert response == connections_response.results

        expected_params = {
            "limit": params.get("limit") or 100,
            "offset": params.get("offset") or 0,
            "order_by": params.get("order_by") or "id",
            "descending": params.get("descending", True),
            "alias": params.get("alias"),
            "connection_protocol": params.get("connection_protocol"),
            "invitation_key": params.get("invitation_key"),
            "invitation_msg_id": params.get("invitation_msg_id"),
            "my_did": params.get("my_did"),
            "state": params.get("state"),
            "their_did": params.get("their_did"),
            "their_public_did": params.get("their_public_did"),
            "their_role": params.get("their_role"),
        }

        mock_aries_controller.connection.get_connections.assert_awaited_once_with(
            **expected_params
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
async def test_get_connections_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.connection.get_connections = AsyncMock(
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

        await get_connections(auth="mocked_auth")

    assert exc.value.status_code == expected_status_code
