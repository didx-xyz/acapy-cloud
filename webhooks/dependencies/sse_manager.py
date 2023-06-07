import asyncio
import logging
from collections import defaultdict as ddict
from contextlib import asynccontextmanager
from typing import Any, Generator, Tuple

from webhooks.dependencies.service import Service

LOGGER = logging.getLogger(__name__)


class SseManager:
    """
    Class to manage Server-Sent Events (SSE).
    """

    def __init__(self, service: Service, max_queue_size=20):
        self.service = service
        self.locks = ddict(asyncio.Lock)  # Concurrency management per wallet
        self.max = max_queue_size

        # The following nested defaultdict stores events per wallet_id, per topic
        self.cache = ddict(lambda: ddict(lambda: asyncio.Queue(maxsize=self.max)))

    @asynccontextmanager
    async def sse_event_stream(
        self, wallet: str, topic: str
    ) -> Generator[asyncio.LifoQueue, Any, None]:
        """
        Create a SSE event stream for a topic using a provided service.

        Args:
            wallet: The ID of the wallet subscribing to the topic.
            topic: The topic for which to create the event stream.
        """
        async with self.locks[wallet]:
            queue_lifo, queue_fifo = await _copy_queue(
                self.cache[wallet][topic], self.max
            )
            self.cache[wallet][topic] = queue_fifo

        yield queue_lifo  # Yield LIFO Queue so newest event are processed first

    async def enqueue_sse_event(self, event: str, wallet: str, topic: str) -> None:
        """
        Enqueue a SSE event to be sent to a specific wallet for a specific topic.

        This function puts the event into the queue of the respective client.

        Args:
            event: The event to enqueue.
            wallet: The ID of the wallet to which to enqueue the event.
            topic: The topic to which to enqueue the event.
        """
        LOGGER.debug(
            "Enqueueing event for wallet '%s': %s",
            wallet,
            event,
        )

        async with self.locks[wallet]:
            # Check if queue is full and make room before adding events
            if self.cache[wallet][topic].full():
                await self.cache[wallet][topic].get()

            await self.cache[wallet][topic].put(event)


async def _copy_queue(
    queue: asyncio.Queue, maxsize: int
) -> Tuple[asyncio.LifoQueue, asyncio.Queue]:
    # Consuming a queue removes its content. Therefore, we create two new queues to copy one
    queue_lifo, queue_fifo = asyncio.LifoQueue(maxsize), asyncio.Queue(maxsize)
    while not queue.empty():
        item = await queue.get()
        await queue_lifo.put(item)
        await queue_fifo.put(item)

    return queue_lifo, queue_fifo
