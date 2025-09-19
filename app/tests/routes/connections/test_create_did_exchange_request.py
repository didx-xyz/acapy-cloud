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


@pytest.fixture
def mock_aries_controller():
    """Create a mock aries controller with default setup."""
    mock_controller = AsyncMock()
    mock_controller.did_exchange.create_request = AsyncMock(
        return_value=created_connection
    )
    mock_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=[])
    )
    return mock_controller


@pytest.fixture
def mock_patches():
    """Setup common patches used across multiple tests."""
    with (
        patch("app.routes.connections.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.connections.conn_record_to_connection",
            return_value=created_connection,
        ) as mock_conn_record,
    ):
        yield mock_client_from_auth, mock_conn_record


def setup_controller_context(mock_client_from_auth, mock_controller):
    """Setup the controller context for the mock client."""
    mock_client_from_auth.return_value.__aenter__.return_value = mock_controller


async def call_create_did_exchange_request(**kwargs):
    """Helper to call create_did_exchange_request with default values."""
    defaults = {
        "their_public_did": test_their_public_did,
        "alias": None,
        "goal": None,
        "goal_code": None,
        "my_label": None,
        "reuse_connection": True,
        "use_did": None,
        "use_did_method": None,
        "use_public_did": False,
        "auth": "mocked_auth",
    }
    defaults.update(kwargs)
    return await create_did_exchange_request(**defaults)


def assert_get_connections_called(mock_controller, should_be_called=True):
    """Assert whether get_connections was called as expected."""
    if should_be_called:
        mock_controller.connection.get_connections.assert_awaited_once_with(
            their_public_did=test_their_public_did
        )
    else:
        mock_controller.connection.get_connections.assert_not_awaited()


def assert_create_request_called(
    mock_controller, should_be_called=True, **expected_params
):
    """Assert whether create_request was called as expected."""
    if should_be_called:
        defaults = {
            "their_public_did": test_their_public_did,
            "alias": None,
            "auto_accept": True,
            "goal": None,
            "goal_code": None,
            "my_label": None,
            "protocol": "didexchange/1.1",
            "use_did": None,
            "use_did_method": None,
            "use_public_did": False,
        }
        defaults.update(expected_params)
        mock_controller.did_exchange.create_request.assert_awaited_once_with(**defaults)
    else:
        mock_controller.did_exchange.create_request.assert_not_awaited()


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
    mock_aries_controller,
    mock_patches,
):
    mock_client_from_auth, mock_conn_record = mock_patches
    setup_controller_context(mock_client_from_auth, mock_aries_controller)

    if not body_params:
        body_params = {}

    response = await call_create_did_exchange_request(
        alias=body_params.get("alias"),
        goal=body_params.get("goal"),
        goal_code=body_params.get("goal_code"),
        my_label=body_params.get("my_label"),
        reuse_connection=body_params.get("reuse_connection", True),
        use_did=body_params.get("use_did"),
        use_did_method=body_params.get("use_did_method"),
        use_public_did=body_params.get("use_public_did", False),
    )

    assert response == created_connection

    assert_create_request_called(
        mock_aries_controller,
        alias=expected_alias,
        goal=body_params.get("goal"),
        goal_code=body_params.get("goal_code"),
        my_label=body_params.get("my_label"),
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
    exception_class,
    expected_status_code,
    expected_detail,
    mock_aries_controller,
    mock_patches,
):
    mock_client_from_auth, mock_conn_record = mock_patches
    mock_aries_controller.did_exchange.create_request = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )
    setup_controller_context(mock_client_from_auth, mock_aries_controller)

    with pytest.raises(HTTPException, match=expected_detail) as exc:
        await call_create_did_exchange_request(alias=None)

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "reuse_connection, existing_connections, should_get_connections, should_create_request, expected_response",
    [
        # When reuse_connection=True and completed connection exists, return existing
        (
            True,
            [
                ConnRecord(
                    connection_id="existing_id",
                    state="completed",
                    rfc23_state="completed",
                    their_did=test_their_public_did,
                )
            ],
            True,
            False,
            "existing_connection",
        ),
        # When reuse_connection=True but only non-completed connections exist, create new
        (
            True,
            [
                ConnRecord(
                    connection_id="non_completed_id",
                    state="request-sent",
                    rfc23_state="request-sent",
                    their_did=test_their_public_did,
                )
            ],
            True,
            True,
            "new_connection",
        ),
        # When reuse_connection=True but no existing connections, create new
        (True, [], True, True, "new_connection"),
        # When reuse_connection=False, always create new (don't check existing)
        (
            False,
            [
                ConnRecord(
                    connection_id="existing_id",
                    state="completed",
                    rfc23_state="completed",
                    their_did=test_their_public_did,
                )
            ],
            False,
            True,
            "new_connection",
        ),
    ],
)
async def test_create_did_exchange_request_reuse_scenarios(
    reuse_connection,
    existing_connections,
    should_get_connections,
    should_create_request,
    expected_response,
    mock_aries_controller,
    mock_patches,
):
    """Test various scenarios for connection reuse behavior."""
    mock_client_from_auth, mock_conn_record = mock_patches

    # Setup existing connections
    mock_aries_controller.connection.get_connections = AsyncMock(
        return_value=AsyncMock(results=existing_connections)
    )

    # Determine expected return value
    if expected_response == "existing_connection" and existing_connections:
        expected_connection = existing_connections[0]
        mock_conn_record.return_value = expected_connection
    else:
        expected_connection = created_connection
        mock_conn_record.return_value = created_connection

    setup_controller_context(mock_client_from_auth, mock_aries_controller)

    response = await call_create_did_exchange_request(reuse_connection=reuse_connection)

    assert response == expected_connection
    assert_get_connections_called(mock_aries_controller, should_get_connections)
    assert_create_request_called(mock_aries_controller, should_create_request)
