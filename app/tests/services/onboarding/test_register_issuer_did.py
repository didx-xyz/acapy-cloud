from logging import Logger
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    ConnRecord,
    InvitationMessage,
    InvitationRecord,
    TransactionRecord,
)

from app.exceptions import CloudApiException
from app.services.onboarding.util.register_issuer_did import (
    wait_endorser_connection_completed,
    wait_for_connection_completion,
    wait_transactions_endorsed,
)


@pytest.mark.anyio
async def test_wait_endorser_connection_completed_happy_path():
    # Mocks
    logger = MagicMock()
    endorser_controller = MagicMock()
    conn_record = ConnRecord(connection_id="abc", rfc23_state="completed")

    # Configure the mock to return a successful connection state
    endorser_controller.connection.get_connections = AsyncMock(
        return_value=MagicMock(results=[conn_record])
    )

    # Invocation
    result = await wait_endorser_connection_completed(
        endorser_controller=endorser_controller,
        invitation_msg_id="test_id",
        logger=logger,
    )

    # Assertions
    assert result.rfc23_state == "completed"
    endorser_controller.connection.get_connections.assert_called_with(
        invitation_msg_id="test_id"
    )
    logger.warning.assert_not_called()
    logger.error.assert_not_called()


@pytest.mark.anyio
async def test_wait_endorser_connection_completed_retry_logic():
    logger = MagicMock()
    endorser_controller = MagicMock()
    conn_record = ConnRecord(connection_id="abc", rfc23_state="completed")

    # First call raises an exception, second call returns the expected state
    endorser_controller.connection.get_connections = AsyncMock(
        side_effect=[Exception("Temporary failure"), MagicMock(results=[conn_record])]
    )

    result = await wait_endorser_connection_completed(
        endorser_controller=endorser_controller,
        invitation_msg_id="test_id",
        logger=logger,
        retry_delay=0.01,
    )

    assert result.rfc23_state == "completed"
    assert endorser_controller.connection.get_connections.call_count == 2
    logger.warning.assert_called_once()
    logger.error.assert_not_called()


@pytest.mark.anyio
async def test_wait_endorser_connection_completed_max_retries_with_exception():
    logger = MagicMock()
    endorser_controller = MagicMock()

    # Always raise an exception
    endorser_controller.connection.get_connections = AsyncMock(
        side_effect=Exception("Persistent failure")
    )

    with pytest.raises(TimeoutError):
        await wait_endorser_connection_completed(
            endorser_controller=endorser_controller,
            invitation_msg_id="test_id",
            logger=logger,
            max_attempts=15,
            retry_delay=0.01,
        )

    assert endorser_controller.connection.get_connections.call_count == 15
    logger.warning.assert_called()
    logger.error.assert_called_with(
        "Maximum number of retries exceeded with exception. Failing."
    )


@pytest.mark.anyio
async def test_wait_endorser_connection_completed_max_retries_no_completion():
    logger = MagicMock()
    endorser_controller = MagicMock()

    # Always return a non-completed state
    conn_record = ConnRecord(connection_id="abc", rfc23_state="not-completed")
    endorser_controller.connection.get_connections = AsyncMock(
        return_value=MagicMock(results=[conn_record])
    )

    with pytest.raises(TimeoutError):
        await wait_endorser_connection_completed(
            endorser_controller=endorser_controller,
            invitation_msg_id="test_id",
            logger=logger,
            max_attempts=15,
            retry_delay=0.01,
        )

    assert endorser_controller.connection.get_connections.call_count == 15
    logger.error.assert_called_with(
        "Maximum number of retries exceeded without returning expected value."
    )


@pytest.mark.anyio
async def test_wait_issuer_did_transaction_endorsed_happy_path():
    logger = MagicMock()
    issuer_controller = MagicMock()
    transaction_record = TransactionRecord(
        connection_id="test_id", state="transaction_acked"
    )

    issuer_controller.endorse_transaction.get_records = AsyncMock(
        return_value=MagicMock(results=[transaction_record])
    )

    # Invocation
    await wait_transactions_endorsed(
        issuer_controller=issuer_controller,
        issuer_connection_id="test_id",
        logger=logger,
    )

    issuer_controller.endorse_transaction.get_records.assert_called()
    logger.warning.assert_not_called()
    logger.error.assert_not_called()


@pytest.mark.anyio
async def test_wait_issuer_did_transaction_endorsed_retry_logic():
    logger = MagicMock()
    issuer_controller = MagicMock()
    transaction_record = TransactionRecord(
        connection_id="test_id", state="transaction_acked"
    )

    issuer_controller.endorse_transaction.get_records = AsyncMock(
        side_effect=[
            Exception("Temporary failure"),
            MagicMock(results=[transaction_record]),
        ]
    )

    await wait_transactions_endorsed(
        issuer_controller=issuer_controller,
        issuer_connection_id="test_id",
        logger=logger,
        retry_delay=0.01,
    )

    assert issuer_controller.endorse_transaction.get_records.call_count == 2
    logger.warning.assert_called_once()
    logger.error.assert_not_called()


@pytest.mark.anyio
async def test_wait_issuer_did_transaction_endorsed_max_retries_with_exception():
    logger = MagicMock()
    issuer_controller = MagicMock()

    issuer_controller.endorse_transaction.get_records = AsyncMock(
        side_effect=Exception("Persistent failure")
    )

    with pytest.raises(TimeoutError):
        await wait_transactions_endorsed(
            issuer_controller=issuer_controller,
            issuer_connection_id="test_id",
            logger=logger,
            max_attempts=15,
            retry_delay=0.01,
        )

    assert issuer_controller.endorse_transaction.get_records.call_count == 15
    logger.warning.assert_called()
    logger.error.assert_called_with(
        "Maximum number of retries exceeded with exception. Failing."
    )


@pytest.mark.anyio
async def test_wait_issuer_did_transaction_endorsed_max_retries_no_ack():
    logger = MagicMock()
    issuer_controller = MagicMock()

    # Always return transactions not in the desired state
    transaction_record = TransactionRecord(connection_id="test_id", state="not_acked")
    issuer_controller.endorse_transaction.get_records = AsyncMock(
        return_value=MagicMock(results=[transaction_record])
    )

    with pytest.raises(TimeoutError):
        await wait_transactions_endorsed(
            issuer_controller=issuer_controller,
            issuer_connection_id="test_id",
            logger=logger,
            max_attempts=15,
            retry_delay=0.01,
        )

    assert issuer_controller.endorse_transaction.get_records.call_count == 15
    logger.error.assert_called_with(
        "Maximum number of retries exceeded while waiting for transaction ack"
    )


@pytest.mark.anyio
async def test_wait_issuer_did_transaction_endorsed_no_transactions():
    logger = MagicMock()
    issuer_controller = MagicMock()

    issuer_controller.endorse_transaction.get_records = AsyncMock(
        return_value=MagicMock(results=[])
    )

    with pytest.raises(TimeoutError):
        await wait_transactions_endorsed(
            issuer_controller=issuer_controller,
            issuer_connection_id="test_id",
            logger=logger,
            max_attempts=15,
            retry_delay=0.01,
        )

    assert issuer_controller.endorse_transaction.get_records.call_count == 15
    logger.error.assert_called_with(
        "Maximum number of retries exceeded with exception. Failing."
    )


@pytest.mark.anyio
async def test_wait_for_connection_completion_timeout():
    # Setup
    issuer_controller = MagicMock()
    issuer_controller.out_of_band.receive_invitation = AsyncMock()
    endorser_controller = MagicMock(spec=AcaPyClient)
    invitation = InvitationRecord(invitation=InvitationMessage())
    logger = MagicMock(spec=Logger)

    # Mock the wait_endorser_connection_completed to raise a TimeoutError
    with patch(
        "app.services.onboarding.util.register_issuer_did.wait_endorser_connection_completed",
        new_callable=AsyncMock,
    ) as mock_wait_endorser_connection_completed:
        mock_wait_endorser_connection_completed.side_effect = TimeoutError

        # Test and assert
        with pytest.raises(CloudApiException) as exc:
            await wait_for_connection_completion(
                issuer_controller=issuer_controller,
                endorser_controller=endorser_controller,
                invitation=invitation,
                logger=logger,
            )

        # Assertions
        assert (
            exc.value.detail
            == "Timeout occurred while waiting for connection with endorser to complete."
        )
        assert exc.value.status_code == 504
        logger.error.assert_called_with(
            "Waiting for invitation complete event has timed out."
        )
