from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import ConnRecord
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.connections import create_did_exchange_request

test_their_public_did = "did:sov:12345"
test_alias = "Test Alias"
test_goal = "Test Goal"
test_goal_code = "TestGoalCode"
test_my_label = "TestLabel"
test_use_did = "did:sov:56789"
test_use_did_method = "did:peer:2"
created_connection = ConnRecord(
    connection_id="some_connection_id",
    state="request-sent",
    their_did=test_their_public_did,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body_params, expected_alias, expected_use_did, expected_use_did_method, expected_use_public_did",
    [
        (None, None, None, None, False),
        ({"use_did": test_use_did}, None, test_use_did, None, False),
        (
            {"use_did_method": test_use_did_method},
            None,
            None,
            test_use_did_method,
            False,
        ),
        ({"use_public_did": True}, None, None, None, True),
        (
            {
                "alias": test_alias,
                "goal": test_goal,
                "goal_code": test_goal_code,
                "my_label": test_my_label,
            },
            test_alias,
            None,
            None,
            False,
        ),
    ],
)
async def test_create_did_exchange_request_success(
    body_params,
    expected_alias,
    expected_use_did,
    expected_use_did_method,
    expected_use_public_did,
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )

    with patch(
        "app.routes.connections.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.routes.connections.conn_record_to_connection",
        return_value=created_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if not body_params:
            body_params = {}

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            alias=body_params.get("alias"),
            goal=body_params.get("goal"),
            goal_code=body_params.get("goal_code"),
            my_label=body_params.get("my_label"),
            use_did=body_params.get("use_did"),
            use_did_method=body_params.get("use_did_method"),
            use_public_did=body_params.get("use_public_did", False),
            auth="mocked_auth",
        )

        assert response == created_connection

        mock_aries_controller.did_exchange.create_request.assert_awaited_once_with(
            their_public_did=test_their_public_did,
            alias=expected_alias,
            auto_accept=True,
            goal=body_params.get("goal"),
            goal_code=body_params.get("goal_code"),
            my_label=body_params.get("my_label"),
            protocol="didexchange/1.1",
            use_did=expected_use_did,
            use_did_method=expected_use_did_method,
            use_public_did=expected_use_public_did,
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
async def test_create_did_exchange_request_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.connections.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException, match=expected_detail
    ) as exc, patch(
        "app.routes.connections.conn_record_to_connection"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_did_exchange_request(
            their_public_did=test_their_public_did,
            alias=None,
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code
