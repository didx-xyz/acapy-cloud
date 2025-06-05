import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.aio.client import Client as NATS
from nats.errors import BadSubscriptionError, Error, TimeoutError
from nats.js.client import JetStreamContext
from nats.js.errors import FetchTimeoutError
from tenacity import RetryCallState

from endorser.services.endorsement_processor import EndorsementProcessor
from shared.constants import (
    ENDORSER_DURABLE_CONSUMER,
    GOVERNANCE_LABEL,
    NATS_STREAM,
    NATS_SUBJECT,
)

# pylint: disable=redefined-outer-name
# because re-using fixtures in same module
# pylint: disable=protected-access
# because we are testing protected methods


@pytest.fixture
async def mock_nats_client():
    with patch("nats.connect") as mock_connect:
        mock_nats = AsyncMock(spec=NATS)
        mock_jetstream = AsyncMock(spec=JetStreamContext)
        mock_nats.jetstream.return_value = mock_jetstream
        mock_connect.return_value = mock_nats
        yield mock_jetstream


@pytest.fixture
def endorsement_processor_mock(mock_nats_client):
    processor = EndorsementProcessor(jetstream=mock_nats_client)

    return processor


@pytest.mark.anyio
async def test_start_and_tasks_are_running(endorsement_processor_mock):
    endorsement_processor_mock._process_endorsement_requests = AsyncMock()

    endorsement_processor_mock.start()
    # Ensure background tasks are started
    assert len(endorsement_processor_mock._tasks) > 0
    assert endorsement_processor_mock.are_tasks_running()


@pytest.mark.anyio
async def test_stop(endorsement_processor_mock):
    # Setup a dummy task to simulate an ongoing task
    dummy_task = asyncio.create_task(asyncio.sleep(1))
    endorsement_processor_mock._tasks.append(dummy_task)

    await endorsement_processor_mock.stop()

    # Check that all tasks were attempted to be cancelled
    assert dummy_task.cancelled()

    # Ensure tasks list is cleared
    assert len(endorsement_processor_mock._tasks) == 0


@pytest.mark.anyio
async def test_are_tasks_running_x(endorsement_processor_mock):
    endorsement_processor_mock._tasks = []
    # Since we didn't start a task, it should be considered not running
    assert not endorsement_processor_mock.are_tasks_running()

    # Create dummy task and stop it
    dummy_done_task = MagicMock()
    dummy_done_task.done.return_value = True
    endorsement_processor_mock._tasks = [dummy_done_task]

    # Task has been cancelled, it should be considered not running
    assert not endorsement_processor_mock.are_tasks_running()

    # Now reset task to appear as still running, to test pubsub thread case
    dummy_done_task.done.return_value = False
    endorsement_processor_mock._tasks = [dummy_done_task]


@pytest.mark.anyio
async def test_process_endorsement_requests_success(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    mock_message = AsyncMock()
    mock_message.data = json.dumps(
        {
            "wallet_id": "governance",
            "topic": "endorsements",
            "origin": "governance",
            "payload": {
                "state": "request-received",
                "transaction_id": "test-txn-id",
            },
        }
    ).encode()
    mock_message.subject = "test.subject"

    # Set up the fetch method to return a message once, then raise asyncio.CancelledError
    mock_subscription.fetch.side_effect = [[mock_message], asyncio.CancelledError]

    # Test
    with patch.object(
        endorsement_processor_mock, "_process_endorsement_event"
    ) as mock_process_event:
        with pytest.raises(asyncio.CancelledError):
            await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    mock_process_event.assert_called_once_with(mock_message.data.decode())
    mock_message.ack.assert_called_once()


@pytest.mark.anyio
async def test_process_endorsement_requests_timeout(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Simulate a timeout, then a CancelledError to stop the loop
    mock_subscription.fetch.side_effect = [FetchTimeoutError, asyncio.CancelledError]

    # Test
    with patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(asyncio.CancelledError):
            await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    mock_sleep.assert_called_once_with(0.1)


@pytest.mark.anyio
async def test_process_endorsement_requests_error(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    mock_message = AsyncMock()
    mock_message.data = b"invalid data"
    mock_message.subject = "test.subject"

    # Return a message that will cause an error, then raise CancelledError
    mock_subscription.fetch.side_effect = [[mock_message], asyncio.CancelledError]

    # Test
    with patch.object(
        endorsement_processor_mock, "_handle_unprocessable_endorse_event"
    ) as mock_handle_error:
        with pytest.raises(asyncio.CancelledError):
            await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    mock_handle_error.assert_called_once()
    assert isinstance(mock_handle_error.call_args[0][2], Exception)


@pytest.mark.anyio
async def test_process_endorsement_requests_multiple_messages(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    mock_messages = [AsyncMock() for _ in range(3)]
    for i, msg in enumerate(mock_messages):
        msg.data = json.dumps(
            {
                "wallet_id": "governance",
                "topic": "endorsements",
                "origin": "governance",
                "payload": {
                    "state": "request-received",
                    "transaction_id": f"test-txn-id-{i}",
                },
            }
        ).encode()
        msg.subject = f"test.subject.{i}"

    # Return multiple messages, then raise CancelledError
    mock_subscription.fetch.side_effect = [mock_messages, asyncio.CancelledError]

    # Test
    with patch.object(
        endorsement_processor_mock, "_process_endorsement_event"
    ) as mock_process_event:
        with pytest.raises(asyncio.CancelledError):
            await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    assert mock_process_event.call_count == 3
    for msg in mock_messages:
        msg.ack.assert_called_once()


@pytest.mark.anyio
async def test_process_endorsement_requests_loop_exit(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Simulate the loop running a few times before we stop it
    side_effects = [
        [AsyncMock(data=b'{"valid": "data"}', subject="test.subject")],
        TimeoutError,
        asyncio.CancelledError,
    ]
    mock_subscription.fetch.side_effect = side_effects

    # Test
    with pytest.raises(asyncio.CancelledError):
        await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    assert mock_subscription.fetch.call_count == 3


@pytest.mark.anyio
async def test_process_endorsement_requests_unexpected_error(
    endorsement_processor_mock, mock_nats_client
):
    # Setup
    mock_subscription = AsyncMock()
    mock_nats_client.pull_subscribe.return_value = mock_subscription

    # Simulate an unexpected exception during message fetching
    mock_subscription.fetch.side_effect = [
        Exception("Unexpected error"),
        asyncio.CancelledError,
    ]

    # Test
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(asyncio.CancelledError):
            await endorsement_processor_mock._process_endorsement_requests()

    # Assertions
    mock_sleep.assert_awaited_once_with(2)


@pytest.mark.anyio
async def test_process_endorsement_event_governance(endorsement_processor_mock):
    governance = GOVERNANCE_LABEL
    event_dict = {
        "origin": governance,
        "wallet_id": governance,
        "topic": "endorsements",
        "payload": {"state": "request-received", "transaction_id": "txn1"},
    }

    event_json = json.dumps(event_dict)

    with (
        patch(
            "endorser.services.endorsement_processor.should_accept_endorsement"
        ) as mock_should_accept_endorsement,
        patch(
            "endorser.services.endorsement_processor.accept_endorsement"
        ) as mock_accept_endorsement,
    ):
        mock_should_accept_endorsement.return_value = MagicMock()
        mock_accept_endorsement.return_value = AsyncMock()
        await endorsement_processor_mock._process_endorsement_event(event_json)

        mock_should_accept_endorsement.assert_called_once()
        mock_accept_endorsement.assert_called_once()


@pytest.mark.anyio
async def test_process_endorsement_event_governance_no_accept(
    endorsement_processor_mock,
):
    governance = GOVERNANCE_LABEL
    event_dict = {
        "origin": governance,
        "wallet_id": governance,
        "topic": "endorsements",
        "payload": {"state": "request-received", "transaction_id": "txn1"},
    }

    event_json = json.dumps(event_dict)

    with (
        patch(
            "endorser.services.endorsement_processor.should_accept_endorsement"
        ) as mock_should_accept_endorsement,
        patch(
            "endorser.services.endorsement_processor.accept_endorsement"
        ) as mock_accept_endorsement,
    ):
        mock_should_accept_endorsement.return_value = False
        mock_accept_endorsement.return_value = AsyncMock()
        await endorsement_processor_mock._process_endorsement_event(event_json)

        mock_should_accept_endorsement.assert_called_once()
        # Assert not accepted:
        mock_accept_endorsement.assert_not_called()


@pytest.mark.anyio
async def test_process_endorsement_event_not_governance(endorsement_processor_mock):
    event_dict = {
        "origin": "not_governance",
        "wallet_id": "not_governance",
        "topic": "endorsements",
        "payload": {"state": "request-received", "transaction_id": "txn1"},
    }

    event_json = json.dumps(event_dict)

    with (
        patch(
            "endorser.services.endorsement_processor.should_accept_endorsement"
        ) as mock_should_accept_endorsement,
        patch(
            "endorser.services.endorsement_processor.accept_endorsement"
        ) as mock_accept_endorsement,
    ):
        mock_accept_endorsement.return_value = AsyncMock()
        await endorsement_processor_mock._process_endorsement_event(event_json)

        # Wallet is not governance; should not call:
        mock_should_accept_endorsement.assert_not_called()
        mock_accept_endorsement.assert_not_called()


@pytest.mark.anyio
async def test_endorsement_processor_subscribe(
    mock_nats_client,
):
    processor = EndorsementProcessor(jetstream=mock_nats_client)
    mock_nats_client.pull_subscribe.return_value = AsyncMock(
        spec=JetStreamContext.PullSubscription
    )

    subscription = await processor._subscribe()
    mock_nats_client.pull_subscribe.assert_called_once_with(
        durable=ENDORSER_DURABLE_CONSUMER,
        subject=f"{NATS_SUBJECT}.endorser.*",
        stream=NATS_STREAM,
    )
    assert isinstance(subscription, JetStreamContext.PullSubscription)


@pytest.mark.anyio
@pytest.mark.parametrize("exception", [BadSubscriptionError, Error, Exception])
async def test_endorsement_processor_subscribe_error(
    mock_nats_client,  # pylint: disable=redefined-outer-name
    exception,
):
    processor = EndorsementProcessor(mock_nats_client)
    mock_nats_client.pull_subscribe.side_effect = exception

    with pytest.raises(exception):
        await processor._subscribe()


@pytest.mark.anyio
async def test_check_jetstream_success(endorsement_processor_mock):
    # Setup
    mock_account_info = AsyncMock()
    mock_account_info.streams = 5
    mock_account_info.consumers = 10
    endorsement_processor_mock.jetstream.account_info.return_value = mock_account_info

    # Test
    result = await endorsement_processor_mock.check_jetstream()

    # Assertions
    assert result == {
        "is_working": True,
        "streams_count": 5,
        "consumers_count": 10,
    }
    endorsement_processor_mock.jetstream.account_info.assert_awaited_once()


@pytest.mark.anyio
async def test_check_jetstream_no_streams(endorsement_processor_mock):
    # Setup
    mock_account_info = AsyncMock()
    mock_account_info.streams = 0
    mock_account_info.consumers = 0
    endorsement_processor_mock.jetstream.account_info.return_value = mock_account_info

    # Test
    result = await endorsement_processor_mock.check_jetstream()

    # Assertions
    assert result == {
        "is_working": False,
        "streams_count": 0,
        "consumers_count": 0,
    }
    endorsement_processor_mock.jetstream.account_info.assert_awaited_once()


@pytest.mark.anyio
async def test_check_jetstream_exception(endorsement_processor_mock):
    # Setup
    endorsement_processor_mock.jetstream.account_info.side_effect = Exception(
        "JetStream error"
    )

    # Test
    with patch("endorser.services.endorsement_processor.logger") as mock_logger:
        result = await endorsement_processor_mock.check_jetstream()

    # Assertions
    assert result == {"is_working": False}
    endorsement_processor_mock.jetstream.account_info.assert_awaited_once()
    mock_logger.exception.assert_called_once_with(
        "Caught exception while checking jetstream status"
    )


class MockFuture:
    """A mock class to simulate the behaviour of a Future object."""

    def __init__(self, exception=None):
        self._exception = exception

    @property
    def failed(self):
        return self._exception is not None

    def exception(self):
        return self._exception


def test_retry_log(endorsement_processor_mock):  # pylint: disable=redefined-outer-name
    # Mock a retry state
    mock_retry_state = MagicMock(spec=RetryCallState)

    # Mock the outcome attribute with a Future-like object
    mock_retry_state.outcome = MockFuture(exception=ValueError("Test retry exception"))
    mock_retry_state.attempt_number = 3  # Retry attempt number

    # Patch the logger to capture log calls
    with patch("endorser.services.endorsement_processor.logger") as mock_logger:
        endorsement_processor_mock._retry_log(  # pylint: disable=protected-access
            retry_state=mock_retry_state
        )

        # Assert that logger.warning was called with the expected message
        mock_logger.warning.assert_called_once_with(
            "Retry attempt {} failed due to {}: {}",
            3,
            "ValueError",
            mock_retry_state.outcome.exception(),
        )
