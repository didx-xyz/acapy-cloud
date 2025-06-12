import asyncio
import importlib
import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from nats.aio.client import Client as NATSClient
from nats.errors import (
    BadSubscriptionError,
    ConnectionClosedError,
    Error,
    NoServersError,
)
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext
from nats.js.errors import FetchTimeoutError

from shared.constants import NATS_STATE_STREAM, NATS_STATE_SUBJECT
from shared.models.webhook_events import CloudApiWebhookEventGeneric
from shared.services.nats_jetstream import init_nats_client
from waypoint.services.nats_service import MAX_TIMEOUT_ERRORS, NatsEventsProcessor

sample_message_data = {
    "wallet_id": "some_wallet_id",
    "group_id": "group_id",
    "origin": "multitenant",
    "topic": "some_topic",
    "payload": {"field": "value", "state": "state"},
}


@pytest.fixture
async def mock_nats_client() -> AsyncGenerator[JetStreamContext, None]:
    with patch("nats.connect") as mock_connect:
        mock_nats = AsyncMock(spec=NATSClient)
        mock_jetstream = AsyncMock(spec=JetStreamContext)
        mock_nats.jetstream.return_value = mock_jetstream
        mock_connect.return_value = mock_nats
        yield mock_jetstream


@pytest.mark.anyio
@pytest.mark.parametrize("nats_creds_file", [None, "some_file"])
async def test_init_nats_client(nats_creds_file) -> None:
    mock_nats_client = AsyncMock(spec=NATSClient)  # pylint: disable=redefined-outer-name

    with (
        patch("nats.connect", return_value=mock_nats_client),
        patch("shared.services.nats_jetstream.NATS_CREDS_FILE", new=nats_creds_file),
    ):
        async for jetstream in init_nats_client():
            assert jetstream == mock_nats_client.jetstream.return_value


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception", [ConnectionClosedError, TimeoutError, NoServersError]
)
async def test_init_nats_client_error(exception) -> None:
    with patch("nats.connect", side_effect=exception):
        with pytest.raises(exception):
            async for _ in init_nats_client():
                pass


@pytest.mark.anyio
async def test_nats_events_processor_subscribe(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock(spec=JetStreamContext.PullSubscription)
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    with patch("waypoint.services.nats_service.ConsumerConfig") as mock_config:
        mock_config.return_value = ConsumerConfig(
            deliver_policy=DeliverPolicy.BY_START_TIME,
            opt_start_time="2024-10-24T09:17:17.998149541Z",
        )

        subscription = await processor._subscribe(  # pylint: disable=protected-access
            group_id="group_id",
            wallet_id="wallet_id",
            topic="proofs",
            state="done",
            start_time="2024-10-24T09:17:17.998149541Z",
            request_uuid="state_uuid",
        )

        mock_nats_client.pull_subscribe.assert_called_once_with(
            subject=f"{NATS_STATE_SUBJECT}.group_id.wallet_id.proofs.done",
            stream=NATS_STATE_STREAM,
            config=mock_config.return_value,
        )
        assert isinstance(subscription, JetStreamContext.PullSubscription)


@pytest.mark.anyio
@pytest.mark.parametrize("exception", [BadSubscriptionError, Error, Exception])
async def test_nats_events_processor_subscribe_error(
    mock_nats_client,  # pylint: disable=redefined-outer-name
    exception,
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_nats_client.pull_subscribe.side_effect = exception

    with pytest.raises(exception):
        await processor._subscribe(  # pylint: disable=protected-access
            group_id="group_id",
            wallet_id="wallet_id",
            topic="proofs",
            state="done",
            start_time="2024-10-24T09:17:17.998149541Z",
            request_uuid="state_uuid",
        )


@pytest.mark.anyio
@pytest.mark.parametrize("group_id", [None, "group_id"])
async def test_process_events(
    mock_nats_client,  # pylint: disable=redefined-outer-name
    group_id,
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    mock_message = AsyncMock()
    mock_message.headers = {"event_topic": "test_topic"}
    mock_message.data = json.dumps(sample_message_data)
    mock_subscription.fetch.return_value = [mock_message]

    stop_event = asyncio.Event()
    async with processor.process_events(
        group_id=group_id,
        wallet_id="wallet_id",
        topic="test_topic",
        state="state",
        stop_event=stop_event,
        duration=0.01,
    ) as event_generator:
        events = []
        async for event in event_generator:
            events.append(event)
            stop_event.set()

    assert len(events) == 1
    assert isinstance(events[0], CloudApiWebhookEventGeneric)
    assert events[0].payload["field"] == "value"

    mock_subscription.fetch.assert_called()
    mock_message.ack.assert_called_once()


@pytest.mark.anyio
async def test_process_events_cancelled_error(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    stop_event = asyncio.Event()

    with patch.object(mock_subscription, "fetch", side_effect=asyncio.CancelledError):
        async with processor.process_events(
            group_id="group_id",
            wallet_id="wallet_id",
            topic="test_topic",
            state="state",
            stop_event=stop_event,
            duration=0.01,
        ) as event_generator:
            events = [event async for event in event_generator]

    assert len(events) == 0
    assert stop_event.is_set()


@pytest.mark.anyio
async def test_process_events_fetch_timeout_error(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    mock_subscription.fetch.side_effect = FetchTimeoutError

    stop_event = asyncio.Event()
    async with processor.process_events(
        group_id="group_id",
        wallet_id="wallet_id",
        topic="test_topic",
        state="state",
        stop_event=stop_event,
        duration=0.01,
    ) as event_generator:
        events = [event async for event in event_generator]

    assert len(events) == 0
    assert stop_event.is_set()


@pytest.mark.anyio
async def test_process_events_timeout_error_handling(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    mock_subscription = AsyncMock()

    # Counter to track the number of TimeoutErrors raised
    timeout_error_count = 0

    # Function to simulate fetch behaviour
    async def fetch_side_effect(**_) -> list[AsyncMock]:
        nonlocal timeout_error_count
        if timeout_error_count < MAX_TIMEOUT_ERRORS:
            timeout_error_count += 1
            raise TimeoutError
        return [AsyncMock(data=json.dumps(sample_message_data))]

    # Mock fetch to raise TimeoutError
    mock_subscription.fetch.side_effect = fetch_side_effect
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Mock the _subscribe method to simulate resubscribe
    mock_resubscribe = AsyncMock(return_value=mock_subscription)
    processor = NatsEventsProcessor(mock_nats_client)
    processor._subscribe = mock_resubscribe  # pylint: disable=protected-access

    stop_event = asyncio.Event()

    # Patch the logger to verify logging calls
    with patch("waypoint.services.nats_service.logger") as mock_logger:
        mock_bound_logger = Mock()
        mock_logger.bind.return_value = mock_bound_logger
        async with processor.process_events(
            group_id="group_id",
            wallet_id="wallet_id",
            topic="test_topic",
            state="state",
            stop_event=stop_event,
            duration=1,
        ) as event_generator:
            events = []
            async for event in event_generator:
                events.append(event)
                stop_event.set()

    # Assert the one event after reconnect yielded
    # assert len(events) == 1
    # assert events[0].payload["field"] == "value"

    # Assert fetch was called
    assert mock_subscription.fetch.call_count == MAX_TIMEOUT_ERRORS + 1

    # Assert unsubscribe was called after max timeout errors
    assert mock_subscription.unsubscribe.called

    # Assert _subscribe was called again after TimeoutError
    assert mock_resubscribe.called

    # Verify that the logger was called with the expected warning
    mock_bound_logger.warning.assert_any_call(
        "Max number of timeout errors reached ({}), attempting to resubscribe...",
        MAX_TIMEOUT_ERRORS,
    )
    mock_bound_logger.info.assert_any_call("Unsubscribed")
    mock_bound_logger.info.assert_any_call("Successfully resubscribed to NATS.")


@pytest.mark.anyio
async def test_process_events_bad_subscription_error_on_unsubscribe(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Mock fetch to raise TimeoutError to trigger unsubscribe logic
    mock_subscription.fetch.side_effect = TimeoutError

    # Mock unsubscribe to raise BadSubscriptionError
    mock_subscription.unsubscribe.side_effect = BadSubscriptionError("Test error")

    # Mock the _subscribe method to simulate resubscribe
    mock_resubscribe = AsyncMock(return_value=mock_subscription)
    processor._subscribe = mock_resubscribe  # pylint: disable=protected-access

    stop_event = asyncio.Event()

    async with processor.process_events(
        group_id="group_id",
        wallet_id="wallet_id",
        topic="test_topic",
        state="state",
        stop_event=stop_event,
        duration=0.01,
    ) as event_generator:
        events = [event async for event in event_generator]

    # Assert no events are yielded
    assert len(events) == 0

    # Assert fetch was called
    assert mock_subscription.fetch.called

    # Assert unsubscribe was called and raised BadSubscriptionError
    assert mock_subscription.unsubscribe.called

    # Assert _subscribe was called again after the unsubscribe error
    assert mock_resubscribe.called


@pytest.mark.anyio
async def test_process_events_base_exception(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Mock fetch to raise a generic exception
    mock_subscription.fetch.side_effect = ArithmeticError("Test base exception")

    stop_event = asyncio.Event()

    # Process events
    with pytest.raises(ArithmeticError):
        events = []
        async with processor.process_events(
            group_id="group_id",
            wallet_id="wallet_id",
            topic="test_topic",
            state="state",
            stop_event=stop_event,
            duration=0.01,
        ) as event_generator:
            events = [event async for event in event_generator]

    # Assert no events are yielded due to the base exception
    assert len(events) == 0

    # Verify unsubscribe was attempted
    mock_subscription.unsubscribe.assert_called_once()

    # Verify fetch was called once before raising the exception
    assert mock_subscription.fetch.call_count == 1


@pytest.mark.anyio
async def test_check_jetstream_working(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_nats_client.account_info.return_value = AsyncMock(streams=2, consumers=5)

    result = await processor.check_jetstream()

    assert result == {
        "is_working": True,
        "streams_count": 2,
        "consumers_count": 5,
    }
    mock_nats_client.account_info.assert_called_once()


@pytest.mark.anyio
async def test_check_jetstream_no_streams(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_nats_client.account_info.return_value = AsyncMock(streams=0, consumers=0)

    result = await processor.check_jetstream()

    assert result == {
        "is_working": False,
        "streams_count": 0,
        "consumers_count": 0,
    }
    mock_nats_client.account_info.assert_called_once()


@pytest.mark.anyio
async def test_check_jetstream_exception(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_nats_client.account_info.side_effect = Exception("Test exception")

    result = await processor.check_jetstream()

    assert result == {"is_working": False}
    mock_nats_client.account_info.assert_called_once()


@pytest.mark.anyio
async def test_retry_logging(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)

    # Create a mock logger
    with patch("waypoint.services.nats_service.logger") as mock_logger:
        # Create a mock retry state
        state = AsyncMock()
        state.outcome = Mock()
        state.outcome.failed = True
        expected_exception = TimeoutError("Test timeout")
        state.outcome.exception.return_value = expected_exception
        state.attempt_number = 3

        # Call the function with the mock retry state
        processor._retry_log(mock_logger, state)  # pylint: disable=protected-access

        # Assert that the logger was called with the expected message
        mock_logger.warning.assert_called_once_with(
            "Retry attempt {} failed due to {}: {}",
            state.attempt_number,
            expected_exception.__class__.__name__,
            expected_exception,
        )


@pytest.mark.anyio
async def test_general_error_handling(
    mock_nats_client,  # pylint: disable=redefined-outer-name
) -> None:
    processor = NatsEventsProcessor(mock_nats_client)
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Mock fetch to raise a generic Error
    mock_subscription.fetch.side_effect = Error("Test error")

    stop_event = asyncio.Event()

    with pytest.raises(Error):
        events = []
        async with processor.process_events(
            group_id="group_id",
            wallet_id="wallet_id",
            topic="test_topic",
            state="state",
            stop_event=stop_event,
            duration=0.01,
        ) as event_generator:
            events = [event async for event in event_generator]

    # Assert no events are yielded due to the error
    assert len(events) == 0

    # Verify unsubscribe was attempted
    mock_subscription.unsubscribe.assert_called_once()


def test_heartbeat_validation() -> None:
    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: (
            "1.0" if key in ["NATS_HEARTBEAT", "NATS_TIMEOUT"] else default
        ),
    ):
        importlib.reload(importlib.import_module("waypoint.services.nats_service"))
        from waypoint.services.nats_service import HEARTBEAT

    assert HEARTBEAT == 0.2  # Should be set to TIMEOUT / 5
