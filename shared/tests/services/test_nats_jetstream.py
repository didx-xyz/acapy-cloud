from unittest.mock import AsyncMock, patch

import pytest

from shared.services.nats_jetstream import NATSStatus


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
