import asyncio
from unittest.mock import ANY, AsyncMock, patch

import pytest
from fastapi import BackgroundTasks, Request
from sse_starlette import EventSourceResponse

from shared.constants import DISCONNECT_CHECK_PERIOD
from shared.models.webhook_events.payloads import CloudApiWebhookEventGeneric
from waypoint.routers.sse import (
    check_disconnect,
    nats_event_stream_generator,
    sse_wait_for_event_with_field_and_state,
)
from waypoint.services.nats_service import NatsEventsProcessor

wallet_id = "wallet123"
topic = "some_topic"
field = "some_field"
field_id = "some_field_id"
desired_state = "some_state"
group_id = "some_group"

dummy_cloudapi_event = CloudApiWebhookEventGeneric(
    wallet_id=wallet_id,
    group_id=group_id,
    topic=topic,
    origin="xyz",
    payload={
        "dummy": "data",
        field: "some_other_field_id",
        "state": "some_other_state",
    },
)

expected_cloudapi_event = CloudApiWebhookEventGeneric(
    wallet_id=wallet_id,
    topic=topic,
    origin="xyz",
    group_id=group_id,
    payload={"dummy": "data", field: field_id, "state": desired_state},
)


@pytest.fixture
def nats_processor_mock():
    mock = AsyncMock(spec=NatsEventsProcessor)
    return mock


@pytest.fixture
def request_mock():
    mock_request = AsyncMock(spec=Request)
    mock_request.is_disconnected.return_value = False
    return mock_request


@pytest.fixture
def async_generator_mock():
    async def _mock_gen(*args):
        for value in args[0]:
            yield value

    return _mock_gen


@pytest.mark.anyio
async def test_check_disconnection():
    request = AsyncMock(spec=Request)
    request.is_disconnected.return_value = True

    stop_event = asyncio.Event()

    task = asyncio.create_task(check_disconnect(request, stop_event))
    await asyncio.sleep(DISCONNECT_CHECK_PERIOD * 1.1)

    assert stop_event.is_set()
    assert task.done() is True


@pytest.mark.anyio
async def test_sse_event_stream_generator_wallet_id_topic_field_desired_state(
    nats_processor_mock,  # pylint: disable=redefined-outer-name
    request_mock,  # pylint: disable=redefined-outer-name
):
    async def mock_event_generator():
        yield expected_cloudapi_event

    nats_processor_mock.process_events.return_value.__aenter__.return_value = (
        mock_event_generator()
    )

    events = [event async for event in nats_event_stream_generator(
        request=request_mock,
        background_tasks=BackgroundTasks(),
        wallet_id=wallet_id,
        topic=topic,
        field=field,
        field_id=field_id,
        desired_state=desired_state,
        group_id=group_id,
        nats_processor=nats_processor_mock,
        look_back=300,
    )]

    assert len(events) == 1
    assert events[0] == expected_cloudapi_event.model_dump_json()


@pytest.mark.anyio
async def test_sse_event_stream_generator_disconnects(
    nats_processor_mock,  # pylint: disable=redefined-outer-name
):
    request = AsyncMock(spec=Request)
    request.is_disconnected.return_value = True

    async def mock_event_generator():
        yield dummy_cloudapi_event
        yield expected_cloudapi_event

    nats_processor_mock.process_events.return_value.__aenter__.return_value = (
        mock_event_generator()
    )

    async for _ in nats_event_stream_generator(
        request=request,
        background_tasks=BackgroundTasks(),
        wallet_id=wallet_id,
        topic=topic,
        field=field,
        field_id=field_id,
        desired_state=desired_state,
        group_id=group_id,
        look_back=300,
        nats_processor=nats_processor_mock,
    ):
        pass

    assert request.is_disconnected.called
    nats_processor_mock.process_events.assert_called_once()


@pytest.mark.anyio
async def test_nats_event_stream_generator_cancelled_error_handling(
    nats_processor_mock,  # pylint: disable=redefined-outer-name
    request_mock,  # pylint: disable=redefined-outer-name
):
    background_tasks = BackgroundTasks()

    async def mock_event_generator():
        raise asyncio.CancelledError
        yield  # Make this function an asynchronous generator

    nats_processor_mock.process_events.return_value.__aenter__.return_value = (
        mock_event_generator()
    )

    generator = nats_event_stream_generator(
        request=request_mock,
        background_tasks=background_tasks,
        wallet_id="wallet123",
        topic="some_topic",
        field="some_field",
        field_id="some_field_id",
        desired_state="some_state",
        group_id="some_group",
        look_back=300,
        nats_processor=nats_processor_mock,
    )

    with pytest.raises(asyncio.CancelledError):
        async for _ in generator:
            pass

    nats_processor_mock.process_events.assert_called_once()
    request_mock.is_disconnected.assert_not_called()


@pytest.mark.anyio
async def test_sse_event_stream(
    async_generator_mock,  # pylint: disable=redefined-outer-name
    nats_processor_mock,  # pylint: disable=redefined-outer-name
    request_mock,  # pylint: disable=redefined-outer-name
):
    with patch(
        "waypoint.routers.sse.nats_event_stream_generator"
    ) as nats_event_stream_generator_mock:
        nats_event_stream_generator_mock.return_value = async_generator_mock(
            [expected_cloudapi_event]
        )

        event_stream = await sse_wait_for_event_with_field_and_state(
            request=request_mock,
            background_tasks=BackgroundTasks(),
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
            desired_state=desired_state,
            group_id=group_id,
            look_back=300,
            nats_processor=nats_processor_mock,
        )

        assert isinstance(event_stream, EventSourceResponse)
        assert event_stream.status_code == 200

        nats_event_stream_generator_mock.assert_called_once_with(
            request=request_mock,
            background_tasks=ANY,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
            desired_state=desired_state,
            group_id=group_id,
            look_back=300,
            nats_processor=nats_processor_mock,
        )
