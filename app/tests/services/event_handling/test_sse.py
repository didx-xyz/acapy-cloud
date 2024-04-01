from typing import Any, AsyncGenerator, Generator, Optional
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from httpx import HTTPError, Response

from app.services.event_handling.sse import (
    sse_subscribe_event_with_field_and_state,
    sse_subscribe_event_with_state,
    sse_subscribe_stream_with_fields,
    sse_subscribe_wallet,
    sse_subscribe_wallet_topic,
    yield_lines_with_disconnect_check,
)
from shared.constants import WEBHOOKS_URL
from shared.util.rich_async_client import RichAsyncClient

wallet_id = "some_wallet"
topic = "some_topic"
field = "some_field"
field_id = "some_field_id"
state = "some_state"


stream_exception_msg = "Stream method exception"


line1 = "data: test\n"
line2 = "\n"
line3 = "data: done\n"
lines_list = [line1, line2, line3]


# Fixture for async generator lines
@pytest.fixture
def async_lines() -> AsyncGenerator[str, Any]:
    async def _lines():
        yield line1
        yield line2
        yield line3

    return _lines


# Fixture for the mock response
@pytest.fixture
def response_mock(
    async_lines: AsyncGenerator[str, Any]  # pylint: disable=redefined-outer-name
) -> AsyncMock:
    response = AsyncMock(spec=Response)
    response.aiter_lines.return_value = async_lines()
    return response


# Fixture for the mock request
@pytest.fixture
def mock_request() -> AsyncMock:
    request = AsyncMock(spec=Request)
    request.is_disconnected.return_value = False
    return request


# Fixture to create and configure the async context manager mock
@pytest.fixture
def configured_async_context_manager_mock(
    response_mock,  # pylint: disable=redefined-outer-name
) -> AsyncMock:
    async_context_manager_mock = AsyncMock()
    async_context_manager_mock.__aenter__.return_value = response_mock
    return async_context_manager_mock


# Fixture to create and configure the async context manager mock to raise an exception
@pytest.fixture
def exception_async_context_manager_mock(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
) -> AsyncMock:
    configured_async_context_manager_mock.__aenter__.side_effect = HTTPError(
        stream_exception_msg
    )
    return configured_async_context_manager_mock


# Patching the yield_lines_with_disconnect_check globally for all tests
@pytest.fixture(autouse=True)
def patch_yield_lines_with_disconnect_check(
    async_lines,  # pylint: disable=redefined-outer-name
) -> Generator[AsyncMock, Any, None]:
    with patch(
        "app.services.event_handling.sse.yield_lines_with_disconnect_check",
        return_value=async_lines(),
    ) as mocked_yield:
        yield mocked_yield


@pytest.mark.anyio
async def test_yield_lines_with_disconnect_check_success(
    response_mock, mock_request  # pylint: disable=redefined-outer-name
):
    # Execute yield_lines_with_disconnect_check and collect results
    results = [
        line
        async for line in yield_lines_with_disconnect_check(mock_request, response_mock)
    ]
    # Assert that all lines were yielded correctly
    assert results == [line1 + "\n", line2 + "\n", line3 + "\n"]


@pytest.mark.anyio
async def test_yield_lines_with_disconnect_check_disconnects(
    response_mock, mock_request  # pylint: disable=redefined-outer-name
):
    # Override the mock request to simulate a disconnection after the first yield
    mock_request.is_disconnected.side_effect = [False, True]

    # Execute yield_lines_with_disconnect_check and collect results
    results = [
        line
        async for line in yield_lines_with_disconnect_check(mock_request, response_mock)
    ]
    # Assert that only the first line was yielded before disconnection
    assert results == [line1 + "\n"]


@pytest.mark.anyio
async def test_sse_subscribe_wallet_exception(
    exception_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
):
    # Patch the stream method of RichAsyncClient to use our prepared context manager mock
    with patch(
        "shared.util.rich_async_client.RichAsyncClient.stream",
        return_value=exception_async_context_manager_mock,
    ):
        mock_request = AsyncMock(spec=Request)
        mock_request.is_disconnected.return_value = False

        # Execute the function and handle the exception
        try:
            results = []
            async for line in sse_subscribe_wallet(
                request=mock_request, group_id=None, wallet_id=wallet_id
            ):
                results.append(line)
            # If no exception is raised, assert False to indicate the test should fail
            assert False, "Expected HTTPError was not raised."
        except HTTPError as e:
            # Assert that an exception is caught, indicating the mocked exception was raised as expected
            assert str(e) == stream_exception_msg


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_sse_subscribe_wallet_success(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
    patch_yield_lines_with_disconnect_check,  # pylint: disable=redefined-outer-name
    group_id: Optional[str],
):
    with patch.object(
        RichAsyncClient,
        "stream",
        return_value=configured_async_context_manager_mock,
    ) as mock_stream:
        # Execute the sse_subscribe_wallet and collect results
        results = []
        async for line in sse_subscribe_wallet(
            request=mock_request, group_id=group_id, wallet_id=wallet_id
        ):
            results.append(line)

        # Verify the collected lines
        assert results == lines_list
        # Ensure the patched yield_lines_with_disconnect_check was called
        patch_yield_lines_with_disconnect_check.assert_called()

        # Additionally, assert that the stream was opened with the correct parameters
        configured_async_context_manager_mock.__aenter__.assert_called()
        mock_stream.assert_called_with(
            "GET",
            f"{WEBHOOKS_URL}/sse/{wallet_id}",
            params={"group_id": group_id} if group_id else None,
        )


@pytest.mark.anyio
async def test_sse_subscribe_wallet_topic_exception(
    exception_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
):
    # Patch the stream method of RichAsyncClient to use our prepared context manager mock
    with patch(
        "shared.util.rich_async_client.RichAsyncClient.stream",
        return_value=exception_async_context_manager_mock,
    ):
        mock_request = AsyncMock(spec=Request)
        mock_request.is_disconnected.return_value = False

        # Execute the function and handle the exception
        try:
            results = []
            async for line in sse_subscribe_wallet_topic(
                request=mock_request,
                group_id=None,
                wallet_id=wallet_id,
                topic="some_topic",
            ):
                results.append(line)
            # If no exception is raised, assert False to indicate the test should fail
            assert False, "Expected HTTPError was not raised."
        except HTTPError as e:
            # Assert that an exception is caught, indicating the mocked exception was raised as expected
            assert str(e) == stream_exception_msg


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_sse_subscribe_wallet_topic_success(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
    patch_yield_lines_with_disconnect_check,  # pylint: disable=redefined-outer-name
    group_id: Optional[str],
):
    with patch.object(
        RichAsyncClient,
        "stream",
        return_value=configured_async_context_manager_mock,
    ) as mock_stream:
        # Execute the sse_subscribe_wallet_topic and collect results
        results = []
        async for line in sse_subscribe_wallet_topic(
            request=mock_request, group_id=group_id, wallet_id=wallet_id, topic=topic
        ):
            results.append(line)

        # Verify the collected lines
        assert results == lines_list
        # Ensure the patched yield_lines_with_disconnect_check was called
        patch_yield_lines_with_disconnect_check.assert_called()

        # Additionally, assert that the stream was opened with the correct parameters
        configured_async_context_manager_mock.__aenter__.assert_called()
        mock_stream.assert_called_with(
            "GET",
            f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}",
            params={"group_id": group_id} if group_id else None,
        )


@pytest.mark.anyio
async def test_sse_subscribe_event_with_state_exception(
    exception_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
):
    # Patch the stream method of RichAsyncClient to use our prepared context manager mock
    with patch(
        "shared.util.rich_async_client.RichAsyncClient.stream",
        return_value=exception_async_context_manager_mock,
    ):
        mock_request = AsyncMock(spec=Request)
        mock_request.is_disconnected.return_value = False

        # Execute the function and handle the exception
        try:
            results = []
            async for line in sse_subscribe_event_with_state(
                request=mock_request,
                group_id=None,
                wallet_id=wallet_id,
                topic=topic,
                desired_state=state,
            ):
                results.append(line)
            # If no exception is raised, assert False to indicate the test should fail
            assert False, "Expected HTTPError was not raised."
        except HTTPError as e:
            # Assert that an exception is caught, indicating the mocked exception was raised as expected
            assert str(e) == stream_exception_msg


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_sse_subscribe_event_with_state_success(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
    patch_yield_lines_with_disconnect_check,  # pylint: disable=redefined-outer-name
    group_id: Optional[str],
):
    with patch.object(
        RichAsyncClient,
        "stream",
        return_value=configured_async_context_manager_mock,
    ) as mock_stream:
        # Execute the sse_subscribe_event_with_state and collect results
        results = []
        async for line in sse_subscribe_event_with_state(
            request=mock_request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            desired_state=state,
        ):
            results.append(line)

        # Verify the collected lines
        assert results == lines_list
        # Ensure the patched yield_lines_with_disconnect_check was called
        patch_yield_lines_with_disconnect_check.assert_called()

        # Additionally, assert that the stream was opened with the correct parameters
        configured_async_context_manager_mock.__aenter__.assert_called()
        mock_stream.assert_called_with(
            "GET",
            f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{state}",
            params={"group_id": group_id} if group_id else None,
        )


@pytest.mark.anyio
async def test_sse_subscribe_stream_with_fields_exception(
    exception_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
):
    # Patch the stream method of RichAsyncClient to use our prepared context manager mock
    with patch(
        "shared.util.rich_async_client.RichAsyncClient.stream",
        return_value=exception_async_context_manager_mock,
    ):
        mock_request = AsyncMock(spec=Request)
        mock_request.is_disconnected.return_value = False

        # Execute the function and handle the exception
        try:
            results = []
            async for line in sse_subscribe_stream_with_fields(
                request=mock_request,
                group_id=None,
                wallet_id=wallet_id,
                topic=topic,
                field=field,
                field_id=field_id,
            ):
                results.append(line)
            # If no exception is raised, assert False to indicate the test should fail
            assert False, "Expected HTTPError was not raised."
        except HTTPError as e:
            # Assert that an exception is caught, indicating the mocked exception was raised as expected
            assert str(e) == stream_exception_msg


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_sse_subscribe_stream_with_fields_success(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
    patch_yield_lines_with_disconnect_check,  # pylint: disable=redefined-outer-name
    group_id: Optional[str],
):
    with patch.object(
        RichAsyncClient,
        "stream",
        return_value=configured_async_context_manager_mock,
    ) as mock_stream:
        # Execute the sse_subscribe_stream_with_fields and collect results
        results = []
        async for line in sse_subscribe_stream_with_fields(
            request=mock_request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
        ):
            results.append(line)

        # Verify the collected lines
        assert results == lines_list
        # Ensure the patched yield_lines_with_disconnect_check was called
        patch_yield_lines_with_disconnect_check.assert_called()

        # Additionally, assert that the stream was opened with the correct parameters
        configured_async_context_manager_mock.__aenter__.assert_called()
        mock_stream.assert_called_with(
            "GET",
            f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{field}/{field_id}",
            params={"group_id": group_id} if group_id else None,
        )


@pytest.mark.anyio
async def test_sse_subscribe_event_with_field_and_state_exception(
    exception_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
):
    # Patch the stream method of RichAsyncClient to use our prepared context manager mock
    with patch(
        "shared.util.rich_async_client.RichAsyncClient.stream",
        return_value=exception_async_context_manager_mock,
    ):
        mock_request = AsyncMock(spec=Request)
        mock_request.is_disconnected.return_value = False

        # Execute the function and handle the exception
        try:
            results = []
            async for line in sse_subscribe_event_with_field_and_state(
                request=mock_request,
                group_id=None,
                wallet_id=wallet_id,
                topic=topic,
                field=field,
                field_id=field_id,
                desired_state=state,
            ):
                results.append(line)
            # If no exception is raised, assert False to indicate the test should fail
            assert False, "Expected HTTPError was not raised."
        except HTTPError as e:
            # Assert that an exception is caught, indicating the mocked exception was raised as expected
            assert str(e) == stream_exception_msg


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "some_group"])
async def test_sse_subscribe_event_with_field_and_state_success(
    configured_async_context_manager_mock,  # pylint: disable=redefined-outer-name
    mock_request,  # pylint: disable=redefined-outer-name
    patch_yield_lines_with_disconnect_check,  # pylint: disable=redefined-outer-name
    group_id: Optional[str],
):
    with patch.object(
        RichAsyncClient,
        "stream",
        return_value=configured_async_context_manager_mock,
    ) as mock_stream:
        # Execute the sse_subscribe_event_with_field_and_state and collect results
        results = []
        async for line in sse_subscribe_event_with_field_and_state(
            request=mock_request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
            desired_state=state,
        ):
            results.append(line)

        # Verify the collected lines
        assert results == lines_list
        # Ensure the patched yield_lines_with_disconnect_check was called
        patch_yield_lines_with_disconnect_check.assert_called()

        # Additionally, assert that the stream was opened with the correct parameters
        configured_async_context_manager_mock.__aenter__.assert_called()
        mock_stream.assert_called_with(
            "GET",
            f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{field}/{field_id}/{state}",
            params={"group_id": group_id} if group_id else None,
        )
