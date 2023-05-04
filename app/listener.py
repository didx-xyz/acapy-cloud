import asyncio
from typing import Any, Dict, Optional

from app.webhooks import Webhooks
from shared_models import CloudApiTopics


class Listener:
    """
    A class for listening to webhook events filtered by topic and wallet_id. Events that match the
    given topic and wallet_id are added to a queue, allowing the caller to wait for specific events
    """

    def __init__(self, topic: CloudApiTopics, wallet_id: str):
        self.topic = topic
        self.wallet_id = wallet_id
        self.queue = asyncio.Queue()

    async def handle_webhook(self, data: Dict[str, Any]):
        """
        Process a webhook event and add it to the queue if the topic and wallet_id match.
        """
        if data["topic"] == self.topic and data["wallet_id"] == self.wallet_id:
            await self.queue.put(data)

    async def wait_for_filtered_event(self, filter_map: Dict[str, Any], timeout: Optional[float] = 180):
        """
        Wait for an event that matches the specified filter_map within the given timeout period.
        """
            """
            Check if the given payload matches the specified filter_map. A payload is considered a
            match if all key-value pairs in the filter_map have the same values in the payload.
            """

        async def _find_matching_event() -> Dict[str, Any]:
            """
            Search the queue for an event that matches the specified filter_map. If a matching event
            is found, return its payload. Otherwise, return None.
            """

            payload = item["payload"]

            if self._payload_matches_filter(payload, filter_map):
                return payload

        # Return None or raise an exception if no matching payload is found
        return None

    async def wait_for_event_with_timeout(self, filter_map: Dict[str, Any], timeout: float = 180):
        try:
            payload = await asyncio.wait_for(_find_matching_event(), timeout=timeout)
            return payload
        except Exception:
            raise
        finally:
            await self.stop()

    async def start(self):
        """
        Start the listener by registering its callback with the Webhooks class.
        """
        await Webhooks.register_callback(self.handle_webhook)

    async def stop(self):
        """
        Stop the listener by unregistering its callback from the Webhooks class.
        """
        Webhooks.unregister_callback(self.handle_webhook)
