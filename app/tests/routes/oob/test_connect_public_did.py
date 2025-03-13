from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnRecord
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.models.oob import ConnectToPublicDid
from app.routes.oob import connect_to_public_did
from shared.models.connection_record import Connection

test_public_did = "did:sov:12345"
created_connection = ConnRecord(
    connection_id="some_connection_id",
    state="request-sent",
    their_did=test_public_did,
)


@pytest.mark.anyio
async def test_connect_to_public_did_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )
    body = ConnectToPublicDid(public_did=test_public_did)
    with patch("app.routes.oob.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.oob.conn_record_to_connection",
        return_value=created_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await connect_to_public_did(
            body=body,
            auth="mocked_auth",
        )

        assert response == created_connection

        mock_aries_controller.did_exchange.create_request.assert_awaited_once_with(
            their_public_did=test_public_did,
        )
