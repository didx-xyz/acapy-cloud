import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aries_cloudcontroller import ConnRecord, TransactionRecord

from app.services.onboarding.util.register_issuer_did import (
    wait_endorser_connection_completed,
    wait_issuer_did_transaction_endorsed,
)


@pytest.mark.anyio
async def test_wait_endorser_connection_completed_happy_path():
    # Mocks
    logger = MagicMock()
    endorser_controller = MagicMock()
    conn_record = ConnRecord(rfc23_state="completed")

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
    conn_record = ConnRecord(rfc23_state="completed")

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

    with pytest.raises(asyncio.TimeoutError):
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
    conn_record = ConnRecord(rfc23_state="not-completed")
    endorser_controller.connection.get_connections = AsyncMock(
        return_value=MagicMock(results=[conn_record])
    )

    with pytest.raises(asyncio.TimeoutError):
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
    await wait_issuer_did_transaction_endorsed(
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

    await wait_issuer_did_transaction_endorsed(
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

    with pytest.raises(asyncio.TimeoutError):
        await wait_issuer_did_transaction_endorsed(
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

    with pytest.raises(asyncio.TimeoutError):
        await wait_issuer_did_transaction_endorsed(
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
