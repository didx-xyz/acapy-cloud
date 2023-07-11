import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket

from app.event_handling.websocket_manager import (
    WebsocketManager,
    WebsocketTimeout,
    convert_url_to_websocket,
)


@pytest.fixture(autouse=True)
def mock_pubsub_client():
    with patch(
        "app.event_handling.websocket_manager.PubSubClient", autospec=True
    ) as mock_client:
        mock_client.return_value.wait_until_ready = AsyncMock()
        mock_client.return_value.disconnect = AsyncMock()
        yield mock_client


@pytest.mark.anyio
async def test_subscribe_wallet_id_and_topic(mock_pubsub_client):
    websocket = AsyncMock(spec=WebSocket)
    wallet_id = "test_wallet_id"
    topic = "test_topic"

    await WebsocketManager.subscribe(websocket, wallet_id=wallet_id, topic=topic)

    # Ensure `subscribe` was called once
    mock_pubsub_client.assert_called_once()
    mock_pubsub_client.return_value.subscribe.assert_called_once()

    # Check that the callback is working as expected
    callback_func = mock_pubsub_client.return_value.subscribe.call_args[0][1]
    dummy_data = "dummy_data"
    dummy_topic = "dummy_topic"
    await callback_func(dummy_data, dummy_topic)

    # Check that the websocket's `send_text` method was called with the correct argument
    websocket.send_text.assert_called_once_with(dummy_data)


@pytest.mark.anyio
async def test_start_pubsub_client_timeout():
    with patch.object(WebsocketManager, "_client", new=None):  # new client
        with patch("asyncio.wait_for", side_effect=timeout_error):
            with patch.object(WebsocketManager, "shutdown", return_value=None):
                with pytest.raises(WebsocketTimeout):
                    await WebsocketManager.start_pubsub_client()


@pytest.mark.anyio
async def test_shutdown_timeout():
    with patch("asyncio.wait_for", side_effect=timeout_error):
        with pytest.raises(WebsocketTimeout):
            await WebsocketManager.shutdown()


async def timeout_error(awaitable, *args, **kwargs):
    await awaitable  # this suppresses warnings of coroutines not being awaited
    raise asyncio.TimeoutError


def test_convert_url_to_websocket():
    assert convert_url_to_websocket("http://example.com") == "ws://example.com"
    assert convert_url_to_websocket("https://example.com") == "wss://example.com"
