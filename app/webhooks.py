import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi_websocket_pubsub import PubSubClient

from app.constants import WEBHOOKS_URL
from shared_models import WEBHOOK_TOPIC_ALL

logger = logging.getLogger(__name__)


class Webhooks:
    """
    A class for managing webhook listeners, emitting webhook events, and handling the underlying
    WebSocket communication.
    """
    _listeners: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
    client: Optional[PubSubClient] = None

    @staticmethod
    async def register_listener(listener: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Register a listener function to be called when a webhook event is received.
        """
        if not Webhooks.client:
            await Webhooks.listen_webhooks()
        Webhooks._listeners.append(listener)

    @staticmethod
    async def emit(data: Dict[str, Any]):
        """
        Emit a webhook event by calling all registered listener functions with the event data.
        """
        for listener in Webhooks._listeners:
            await listener(data)

    @staticmethod
    def unregister_listener(listener: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Unregister a listener function so that it will no longer be called when a webhook event is received.
        """
        try:
            Webhooks._listeners.remove(listener)
        except ValueError:
            # Listener not in list
            pass

    @staticmethod
    async def listen_webhooks(timeout: float = 30):
        """
        Start listening for webhook events on a WebSocket connection with a specified timeout.
        """
        async def wait_for_ready():
            Webhooks.client = PubSubClient(
                [WEBHOOK_TOPIC_ALL], callback=Webhooks._on_webhook
            )

            ws_url = WEBHOOKS_URL
            if ws_url.startswith("http"):
                ws_url = "ws" + ws_url[4:]

            Webhooks.client.start_client(ws_url + "/pubsub")
            await Webhooks.client.wait_until_ready()

        try:
            await asyncio.wait_for(wait_for_ready(), timeout=timeout)
        except asyncio.TimeoutError:
            if Webhooks.client:
                await Webhooks.client.disconnect()
            raise WebhooksShutdownTimeout(
                f"Webhooks shutdown timed out ({timeout}s)")

    @staticmethod
    async def _on_webhook(data: str, topic: str):
        """
        Internal callback function for handling received webhook events.
        """
        await Webhooks.emit(json.loads(data))

    @staticmethod
    async def shutdown(timeout: float = 20):
        """
        Shutdown the Webhooks client and clear the listeners with a specified timeout.
        """
        async def wait_for_shutdown():
            if Webhooks.client:
                await Webhooks.client.disconnect()
                Webhooks.client = None

            Webhooks._listeners = []

        try:
            await asyncio.wait_for(wait_for_shutdown(), timeout=timeout)
        except asyncio.TimeoutError:
            raise WebhooksShutdownTimeout(
                f"Webhooks shutdown timed out ({timeout}s)")


class WebhooksShutdownTimeout(Exception):
    """Exception raised when the Webhooks shutdown times out."""
    pass
