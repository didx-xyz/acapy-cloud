from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.routes.sse import get_sse_subscribe_event_with_field_and_state

wallet_id = "some_wallet"
topic = "some_topic"
field = "some_field"
field_id = "some_field_id"
state = "some_state"


@pytest.fixture()
def mock_request() -> Mock:
    return Mock()


@pytest.fixture()
def mock_auth() -> Mock:
    return Mock()


@pytest.fixture()
def mock_verify_wallet_access() -> AsyncMock:
    with patch("app.routes.sse.verify_wallet_access", new=Mock()) as mocked:
        yield mocked


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_get_sse_subscribe_event_with_field_and_state(
    mock_request,  # pylint: disable=redefined-outer-name
    mock_auth,  # pylint: disable=redefined-outer-name
    mock_verify_wallet_access,  # pylint: disable=redefined-outer-name
    group_id: str | None,
) -> None:
    # Mock sse_subscribe_event_with_field_and_state function to not actually attempt to connect to an SSE stream
    sse_subscribe_event_with_field_and_state_mock = Mock()

    with patch(
        "app.routes.sse.sse_subscribe_event_with_field_and_state",
        new=sse_subscribe_event_with_field_and_state_mock,
    ):
        # Call the route handler function
        response = await get_sse_subscribe_event_with_field_and_state(
            request=mock_request,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
            desired_state=state,
            group_id=group_id,
            auth=mock_auth,
            look_back=300,
        )

    assert response.media_type == "text/event-stream"

    # Assert that verify_wallet_access and sse_subscribe_event_with_field_and_state called with the correct parameters
    mock_verify_wallet_access.assert_called_with(mock_auth, wallet_id)
    sse_subscribe_event_with_field_and_state_mock.assert_called_with(
        request=mock_request,
        wallet_id=wallet_id,
        group_id=group_id,
        topic=topic,
        field=field,
        field_id=field_id,
        desired_state=state,
        look_back=300,
    )
