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

test_their_public_did = "did:cheqd:12345"
test_alias = "Test Alias"
test_goal = "Test Goal"
test_goal_code = "TestGoalCode"
test_my_label = "TestLabel"
test_use_did = "did:cheqd:56789"
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
    # Mock get_connections to return no existing connections
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[])
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

        if not body_params:
            body_params = {}

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            alias=body_params.get("alias"),
            goal=body_params.get("goal"),
            goal_code=body_params.get("goal_code"),
            my_label=body_params.get("my_label"),
            reuse_connection=body_params.get("reuse_connection", True),
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
    # Mock get_connections to return no existing connections
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[])
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        pytest.raises(HTTPException, match=expected_detail) as exc,
        patch("app.routes.connections.conn_record_to_connection"),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_did_exchange_request(
            their_public_did=test_their_public_did,
            alias=None,
            reuse_connection=True,
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_create_did_exchange_request_returns_existing_completed_connection():
    """Test that when reuse_connection=True and completed connections exist, it returns the existing one."""
    existing_connection = ConnRecord(
        connection_id="existing_connection_id",
        state="completed",
        rfc23_state="completed",
        their_did=test_their_public_did,
    )

    mock_aries_controller = AsyncMock()
    # Mock get_connections to return an existing completed connection
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[existing_connection])
    )
    # This should not be called since we return existing connection
    mock_aries_controller.did_exchange.create_request = AsyncMock()

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=existing_connection,
        ) as mock_conn_record_to_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            reuse_connection=True,
            auth="mocked_auth",
        )

        assert response == existing_connection

        # Verify get_connections was called to check for existing connections
        mock_aries_controller.connection.get_connections.assert_awaited_once_with(
            their_public_did=test_their_public_did
        )

        # Verify create_request was NOT called since we returned existing connection
        mock_aries_controller.did_exchange.create_request.assert_not_awaited()

        # Verify conn_record_to_connection was called with existing connection
        mock_conn_record_to_connection.assert_called_once_with(existing_connection)


@pytest.mark.anyio
async def test_create_did_exchange_request_creates_new_when_existing_not_completed():
    """Test that when reuse_connection=True but only non-completed connections exist, it creates a new one."""
    existing_non_completed_connection = ConnRecord(
        connection_id="existing_non_completed_id",
        state="request-sent",
        rfc23_state="request-sent",
        their_did=test_their_public_did,
    )

    mock_aries_controller = AsyncMock()
    # Mock get_connections to return an existing non-completed connection
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[existing_non_completed_connection])
    )
    # This should be called since no completed connections exist
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=created_connection,
        ) as mock_conn_record_to_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            reuse_connection=True,
            auth="mocked_auth",
        )

        assert response == created_connection

        # Verify get_connections was called to check for existing connections
        mock_aries_controller.connection.get_connections.assert_awaited_once_with(
            their_public_did=test_their_public_did
        )

        # Verify create_request was called since no completed connections exist
        mock_aries_controller.did_exchange.create_request.assert_awaited_once_with(
            their_public_did=test_their_public_did,
            alias=None,
            auto_accept=True,
            goal=None,
            goal_code=None,
            my_label=None,
            protocol="didexchange/1.1",
            use_did=None,
            use_did_method=None,
            use_public_did=False,
        )

        # Verify conn_record_to_connection was called with new connection
        mock_conn_record_to_connection.assert_called_once_with(created_connection)


@pytest.mark.anyio
async def test_create_did_exchange_request_ignores_existing_when_reuse_false():
    """Test that when reuse_connection=False, it always creates a new connection
    even if existing ones exist.
    """
    existing_completed_connection = ConnRecord(
        connection_id="existing_completed_id",
        state="completed",
        rfc23_state="completed",
        their_did=test_their_public_did,
    )

    mock_aries_controller = AsyncMock()
    # Mock get_connections - this should NOT be called when reuse_connection=False
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[existing_completed_connection])
    )
    # This should be called regardless of existing connections
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=created_connection,
        ) as mock_conn_record_to_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            reuse_connection=False,
            auth="mocked_auth",
        )

        assert response == created_connection

        # Verify get_connections was NOT called since reuse_connection=False
        mock_aries_controller.connection.get_connections.assert_not_awaited()

        # Verify create_request was called to create new connection
        mock_aries_controller.did_exchange.create_request.assert_awaited_once_with(
            their_public_did=test_their_public_did,
            alias=None,
            auto_accept=True,
            goal=None,
            goal_code=None,
            my_label=None,
            protocol="didexchange/1.1",
            use_did=None,
            use_did_method=None,
            use_public_did=False,
        )

        # Verify conn_record_to_connection was called with new connection
        mock_conn_record_to_connection.assert_called_once_with(created_connection)


@pytest.mark.anyio
async def test_create_did_exchange_request_creates_new_when_no_existing_connections():
    """Test that when reuse_connection=True but no existing connections exist, it creates a new one."""
    mock_aries_controller = AsyncMock()
    # Mock get_connections to return no existing connections
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[])
    )
    # This should be called since no existing connections exist
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )

    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=created_connection,
        ) as mock_conn_record_to_connection,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await create_did_exchange_request(
            their_public_did=test_their_public_did,
            reuse_connection=True,
            auth="mocked_auth",
        )

        assert response == created_connection

        # Verify get_connections was called to check for existing connections
        mock_aries_controller.connection.get_connections.assert_awaited_once_with(
            their_public_did=test_their_public_did
        )

        # Verify create_request was called since no existing connections exist
        mock_aries_controller.did_exchange.create_request.assert_awaited_once_with(
            their_public_did=test_their_public_did,
            alias=None,
            auto_accept=True,
            goal=None,
            goal_code=None,
            my_label=None,
            protocol="didexchange/1.1",
            use_did=None,
            use_did_method=None,
            use_public_did=False,
        )

        # Verify conn_record_to_connection was called with new connection
        mock_conn_record_to_connection.assert_called_once_with(created_connection)
