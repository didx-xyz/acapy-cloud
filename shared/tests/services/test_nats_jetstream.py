from unittest.mock import AsyncMock, Mock, patch

import pytest
from nats.errors import (
    AuthorizationError,
    ConnectionClosedError,
    NoServersError,
    TimeoutError,
    UnexpectedEOF,
)

from shared.services.nats_jetstream import (
    MAX_ATTEMPTS_BEFORE_ERROR,
    NATSStatus,
    init_nats_client,
)


@pytest.mark.anyio
async def test_nats_status_error_callback():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.error_callback(Exception("Test error"))
        mock_logger.error.assert_called()


@pytest.mark.anyio
async def test_nats_status_disconnected_callback():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.disconnected_callback()
        mock_logger.warning.assert_called()


@pytest.mark.anyio
async def test_nats_status_reconnected_callback():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.reconnected_callback()
        mock_logger.info.assert_called()


@pytest.mark.anyio
async def test_nats_status_closed_callback():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.closed_callback()
        mock_logger.info.assert_called()


@pytest.mark.anyio
async def test_init_nats_client_with_creds():
    with (
        patch("shared.services.nats_jetstream.NATS_CREDS_FILE", "test_creds.conf"),
        patch("shared.services.nats_jetstream.nats.connect") as mock_connect,
    ):
        mock_connect.return_value = AsyncMock(
            jetstream=Mock(return_value="jetstream_context")
        )

        async for js in init_nats_client():
            assert js == "jetstream_context"

        # Verify connect was called with credentials
        connect_kwargs = mock_connect.call_args[1]
        assert connect_kwargs["user_credentials"] == "test_creds.conf"


@pytest.mark.anyio
async def test_init_nats_client_without_creds():
    with (
        patch("shared.services.nats_jetstream.NATS_CREDS_FILE", None),
        patch(
            "shared.services.nats_jetstream.nats.connect", AsyncMock()
        ) as mock_connect,
        patch("shared.services.nats_jetstream.logger") as mock_logger,
    ):
        mock_connect.return_value = AsyncMock(
            jetstream=Mock(return_value="jetstream_context")
        )

        async for js in init_nats_client():
            assert js == "jetstream_context"

        # Verify connect was called without credentials
        connect_kwargs = mock_connect.call_args[1]
        assert "user_credentials" not in connect_kwargs
        mock_logger.warning.assert_called_with(
            "No NATS credentials file found, assuming local development"
        )


@pytest.mark.anyio
async def test_init_nats_client_connection_error():
    with (
        patch("shared.services.nats_jetstream.NATS_CREDS_FILE", None),
        patch("shared.services.nats_jetstream.nats.connect") as mock_connect,
        patch("shared.services.nats_jetstream.logger") as mock_logger,
    ):
        mock_connect.side_effect = NoServersError()

        with pytest.raises(NoServersError):
            async for _ in init_nats_client():
                pass

        mock_logger.error.assert_called_with(
            "Failed to establish initial NATS connection: {}", mock_connect.side_effect
        )


@pytest.mark.anyio
async def test_nats_status_error_callback_unexpected_eof():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        exc = UnexpectedEOF()
        await nats_status.error_callback(exc)
        mock_logger.warning.assert_called_with("NATS unexpected EOF error: {}", exc)


@pytest.mark.parametrize(
    "exc", [NoServersError(), TimeoutError(), ConnectionClosedError()]
)
@pytest.mark.anyio
async def test_nats_status_error_callback_connection_issues(exc):
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.error_callback(exc)
        mock_logger.error.assert_called_with("Critical NATS connection issue: {}", exc)


@pytest.mark.anyio
async def test_nats_status_error_callback_auth_error():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        exc = AuthorizationError()
        await nats_status.error_callback(exc)
        mock_logger.error.assert_called_with(
            "NATS authentication/authorization failure: {}", exc
        )


@pytest.mark.anyio
async def test_nats_status_error_callback_empty_response():
    nats_status = NATSStatus()
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        exc = Exception("empty response from server")
        await nats_status.error_callback(exc)
        mock_logger.error.assert_called_with(
            "NATS server unavailable during connection attempt: {}",
            exc,
        )


@patch("shared.services.nats_jetstream.time.time", return_value=1000)
@pytest.mark.anyio
async def test_nats_status_error_callback_during_reconnect(mock_time):
    nats_status = NATSStatus()
    nats_status.last_disconnect_time = 1000 - 2  # 2 seconds ago
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        exc = Exception("some error")
        await nats_status.error_callback(exc)
        mock_logger.warning.assert_called_with(
            "NATS operational error during reconnection: {}", exc
        )
    mock_time.assert_called_once()


@patch("shared.services.nats_jetstream.time.time", return_value=1000)
@pytest.mark.anyio
async def test_nats_status_error_callback_after_reconnect_threshold(mock_time):
    nats_status = NATSStatus()
    nats_status.last_disconnect_time = 1000 - 10  # 10 seconds ago
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        exc = Exception("some error")
        await nats_status.error_callback(exc)
        mock_logger.error.assert_called_with(
            "NATS operational error. Exceeded reconnect ({}s): {}",
            10,
            exc,
        )
    mock_time.assert_called_once()


@pytest.mark.anyio
async def test_nats_status_disconnected_callback_max_attempts():
    nats_status = NATSStatus()
    nats_status.reconnect_attempts = MAX_ATTEMPTS_BEFORE_ERROR
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.disconnected_callback()
        mock_logger.error.assert_called_with(
            "Persistent NATS disconnection after {} attempts; cluster may be unavailable",
            MAX_ATTEMPTS_BEFORE_ERROR + 1,
        )


@patch("shared.services.nats_jetstream.time.time", return_value=1000)
@pytest.mark.anyio
async def test_nats_status_reconnected_callback_within_threshold(mock_time):
    nats_status = NATSStatus()
    nats_status.last_disconnect_time = 1000 - 1  # 1 second ago
    nats_status.reconnect_attempts = 0
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.reconnected_callback()
        mock_logger.info.assert_called_with(
            "Reconnected to NATS server after: {}s",
            1,
        )
    mock_time.assert_called_once()


@patch("shared.services.nats_jetstream.time.time", return_value=1000)
@pytest.mark.anyio
async def test_nats_status_reconnected_callback_after_delay(mock_time):
    nats_status = NATSStatus()
    nats_status.last_disconnect_time = 1000 - 10  # 10 seconds ago
    nats_status.reconnect_attempts = 2
    with patch("shared.services.nats_jetstream.logger") as mock_logger:
        await nats_status.reconnected_callback()
        mock_logger.warning.assert_called_with(
            "Reconnected to NATS server after delay or multiple attempts: {}s, attempts={}",
            10,
            2,
        )
    mock_time.assert_called_once()
