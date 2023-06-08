import asyncio
import logging
import time
from collections import defaultdict as ddict
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Generator, Tuple

from shared import TopicItem
from webhooks.dependencies.service import Service

LOGGER = logging.getLogger(__name__)

MAX_EVENT_AGE_SECONDS = 15
MAX_QUEUE_SIZE = 50


class SseManager:
    """
    Class to manage Server-Sent Events (SSE).
    """

    def __init__(self, service: Service, max_queue_size=MAX_QUEUE_SIZE):
        self.service = service
        self.locks = ddict(lambda: ddict(asyncio.Lock))  # Concurrency per wallet/topic
        self.max = max_queue_size

        # The following nested defaultdict stores events per wallet_id, per topic
        self.fifo_cache = ddict(lambda: ddict(lambda: asyncio.Queue(self.max)))
        self.lifo_cache = ddict(lambda: ddict(lambda: asyncio.LifoQueue(self.max)))
        # Last In First Out Queue is to be used for consumption, so that newest events are yielded first
        # FIFO Queue maintains order of events and is used to repopulate LIFO queue after consumption

    @asynccontextmanager
    async def sse_event_stream(
        self, wallet: str, topic: str, duration: int = 0
    ) -> Generator[AsyncGenerator[TopicItem, Any], Any, None]:
        """
        Create a SSE stream of events for a wallet_id on a specific topic

        Args:
            wallet: The ID of the wallet subscribing to the topic.
            topic: The topic for which to create the event stream.
            duration: Timeout duration in seconds. 0 means no timeout.
        """
        async with self.locks[wallet][topic]:
            lifo_queue = self.lifo_cache[wallet][topic]

        async def event_generator() -> Generator[TopicItem, Any, None]:
            start_time = time.time()
            while True:
                try:
                    timestamp, event = await asyncio.wait_for(
                        lifo_queue.get(), timeout=1
                    )
                    if time.time() - timestamp > MAX_EVENT_AGE_SECONDS:
                        continue
                    yield event
                except asyncio.TimeoutError:
                    if duration > 0 and time.time() - start_time > duration:
                        LOGGER.info("\nSSE Event Stream: closing with timeout error")
                        break

        try:
            yield event_generator()
        finally:
            async with self.locks[wallet][topic]:
                # LIFO cache has been consumed; repopulate with events from FIFO cache:
                lifo_queue, fifo_queue = await _copy_queue(
                    self.fifo_cache[wallet][topic], self.max
                )
                self.fifo_cache[wallet][topic] = fifo_queue
                self.lifo_cache[wallet][topic] = lifo_queue

    async def enqueue_sse_event(
        self, event: TopicItem, wallet: str, topic: str
    ) -> None:
        """
        Enqueue a SSE event to be sent to a specific wallet for a specific topic.

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

        async with self.locks[wallet][topic]:
            # Check if queue is full and make room before adding events
            if self.fifo_cache[wallet][topic].full():
                await self.fifo_cache[wallet][topic].get()

                # cannot pop from lifo queue; rebuild from fifo queue
                lifo_queue, fifo_queue = await _copy_queue(
                    self.fifo_cache[wallet][topic], self.max
                )
                self.fifo_cache[wallet][topic] = fifo_queue
                self.lifo_cache[wallet][topic] = lifo_queue

            timestamped_event: Tuple(float, TopicItem) = (time.time(), event)
            await self.lifo_cache[wallet][topic].put(timestamped_event)
            await self.fifo_cache[wallet][topic].put(timestamped_event)


async def _copy_queue(
    queue: asyncio.Queue, maxsize: int
) -> Tuple[asyncio.LifoQueue, asyncio.Queue]:
    # Consuming a queue removes its content. Therefore, we create two new queues to copy one
    lifo_queue, fifo_queue = asyncio.LifoQueue(maxsize), asyncio.Queue(maxsize)
    while not queue.empty():
        timestamp, item = await queue.get()
        if (
            time.time() - timestamp <= MAX_EVENT_AGE_SECONDS
        ):  # only copy events that are less than a minute old
            await lifo_queue.put((timestamp, item))
            await fifo_queue.put((timestamp, item))

    return lifo_queue, fifo_queue
