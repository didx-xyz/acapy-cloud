import asyncio
import time
from collections import defaultdict as ddict
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, List, NoReturn, Tuple

from pydantic import ValidationError

from shared.constants import (
    CLIENT_QUEUE_POLL_PERIOD,
    MAX_EVENT_AGE_SECONDS,
    MAX_QUEUE_SIZE,
    QUEUE_CLEANUP_PERIOD,
)
from shared.log_config import get_logger
from shared.models.webhook_topics import WEBHOOK_TOPIC_ALL, CloudApiWebhookEventGeneric
from webhooks.dependencies.event_generator_wrapper import EventGeneratorWrapper
from webhooks.dependencies.redis_service import RedisService
from webhooks.dependencies.websocket import publish_event_on_websocket

logger = get_logger(__name__)


class SseManager:
    """
    Class to manage Server-Sent Events (SSE).
    """

    def __init__(self, redis_service: RedisService) -> None:
        self.redis_service = redis_service

        # Define incoming events queue, to decouple the process of receiving events,
        # from the process of storing them in the per-wallet queues
        self.incoming_events = asyncio.Queue()

        # The following nested defaultdict stores events per wallet_id, per topic
        self.fifo_cache = ddict(
            lambda: ddict(lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE))
        )
        self.lifo_cache = ddict(
            lambda: ddict(lambda: asyncio.LifoQueue(maxsize=MAX_QUEUE_SIZE))
        )
        # Last In First Out Queue is to be used for consumption, so that newest events are yielded first
        # FIFO Queue maintains order of events and is used to repopulate LIFO queue after consumption

        # Concurrency per wallet/topic
        self.cache_locks = ddict(lambda: ddict(asyncio.Lock))

        # To clean up queues that are no longer used
        self._cache_last_accessed = ddict(lambda: ddict(datetime.now))

        self._start_background_tasks()

    def _start_background_tasks(self) -> None:
        """
        Start the background tasks as part of SseManager's lifecycle
        """
        # backfill previous events from redis, if any
        asyncio.create_task(self._backfill_events())

        # listen for new events on redis pubsub channel
        asyncio.create_task(self._listen_for_new_events())

        # process incoming events and cleanup queues
        asyncio.create_task(self._process_incoming_events())
        asyncio.create_task(self._cleanup_cache())

    async def _listen_for_new_events(self) -> NoReturn:
        """
        Listen on redis pubsub channel for new SSE events; read the event and add to queue
        """
        pubsub = self.redis_service.redis.pubsub()

        await pubsub.subscribe(self.redis_service.sse_event_pubsub_channel)

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                try:
                    message_data = message["data"]
                    if isinstance(message_data, bytes):
                        message_data = message_data.decode("utf-8")

                    wallet_id, timestamp_ns_str = message_data.split(":")
                    timestamp_ns = int(timestamp_ns_str)

                    # Fetch the event with the exact timestamp from the sorted set
                    json_events = await self.redis_service.get_json_events_by_timestamp(
                        wallet_id, timestamp_ns, timestamp_ns
                    )

                    for json_event in json_events:
                        try:
                            parsed_event = (
                                CloudApiWebhookEventGeneric.model_validate_json(
                                    json_event
                                )
                            )
                            topic = parsed_event.topic

                            # Add event to SSE queue for processing
                            await self.incoming_events.put(parsed_event)

                            # Also publish event to websocket
                            # Doing it here makes websockets stateless as well
                            await publish_event_on_websocket(
                                event_json=json_event,
                                wallet_id=wallet_id,
                                topic=topic,
                            )
                        except ValidationError as e:
                            error_message = (
                                "Could not parse json event retreived from redis "
                                f"into a `CloudApiWebhookEventGeneric`. Error: `{str(e)}`."
                            )
                            logger.error(error_message)

                except (KeyError, ValueError) as e:
                    logger.error("Could not unpack redis pubsub message: {}", e)
                except Exception:
                    logger.exception("Exception caught while processing redis event")
            else:
                await asyncio.sleep(0.01)  # Prevent a busy loop if no new messages

    async def _backfill_events(self) -> None:
        """
        Backfill events from Redis that were published within the MAX_EVENT_AGE window.
        """
        logger.info("Start backfilling SSE queue with recent events from redis")
        try:
            # Calculate the minimum timestamp for backfilling
            current_time_ns = time.time_ns()  # Current time in nanoseconds
            min_timestamp_ns = current_time_ns - (MAX_EVENT_AGE_SECONDS * 1e9)
            logger.debug(f"Backfilling events from timestamp_ns: {min_timestamp_ns}")

            # Get all wallets to backfill events for
            wallets = await self.redis_service.get_all_wallet_ids()

            total_events_backfilled = 0
            for wallet_id in wallets:
                # Fetch events within the time window from Redis for each wallet
                events = await self.redis_service.get_events_by_timestamp(
                    wallet_id, min_timestamp_ns, "+inf"
                )

                # Enqueue the fetched events
                for event in events:
                    await self.incoming_events.put(event)
                    total_events_backfilled += 1

            logger.info(f"Backfilled a total of {total_events_backfilled} events.")
        except Exception as e:
            logger.exception("Exception caught during backfilling events: {}", e)

    async def _process_incoming_events(self) -> NoReturn:
        while True:
            # Wait for an event to be added to the incoming events queue
            event: CloudApiWebhookEventGeneric = await self.incoming_events.get()
            wallet = event.wallet_id
            topic = event.topic

            # Process the event into the per-wallet queues
            async with self.cache_locks[wallet][topic]:
                # Check if queue is full and make room before adding events
                if self.fifo_cache[wallet][topic].full():
                    logger.warning(
                        "SSE Manager: fifo_cache is full for wallet `{}` and topic `{}` with max queue length `{}`",
                        wallet,
                        topic,
                        MAX_QUEUE_SIZE,
                    )

                    await self.fifo_cache[wallet][topic].get()

                    # cannot pop from lifo queue; rebuild from fifo queue
                    lifo_queue, fifo_queue = await _copy_queue(
                        self.fifo_cache[wallet][topic]
                    )
                    self.fifo_cache[wallet][topic] = fifo_queue
                    self.lifo_cache[wallet][topic] = lifo_queue

                timestamped_event: Tuple(float, CloudApiWebhookEventGeneric) = (
                    time.time(),
                    event,
                )
                logger.trace(
                    "Putting event on cache for wallet `{}`, topic `{}`: {}",
                    wallet,
                    topic,
                    event,
                )
                await self.lifo_cache[wallet][topic].put(timestamped_event)
                await self.fifo_cache[wallet][topic].put(timestamped_event)

    async def sse_event_stream(
        self,
        *,
        wallet: str,
        topic: str,
        stop_event: asyncio.Event,
        duration: int = 0,
    ) -> EventGeneratorWrapper:
        """
        Create a SSE stream of events for a wallet_id on a specific topic

        Args:
            wallet: The ID of the wallet subscribing to the topic.
            topic: The topic for which to create the event stream.
            stop_event: An asyncio.Event to signal a stop request
            duration: Timeout duration in seconds. 0 means no timeout.
        """
        client_queue = asyncio.Queue()

        populate_task = asyncio.create_task(
            self._populate_client_queue(
                wallet=wallet,
                topic=topic,
                client_queue=client_queue,
            )
        )

        async def event_generator() -> AsyncGenerator[CloudApiWebhookEventGeneric, Any]:
            bound_logger = logger.bind(body={"wallet": wallet, "topic": topic})
            bound_logger.debug("SSE Manager: Starting event_generator")
            end_time = time.time() + duration if duration > 0 else None
            remaining_time = None
            while not stop_event.is_set():
                try:
                    if end_time:
                        remaining_time = end_time - time.time()
                        if remaining_time <= 0:
                            bound_logger.debug(
                                "Event generator timeout: remaining_time < 0"
                            )
                            stop_event.set()
                            break
                    event = await asyncio.wait_for(
                        client_queue.get(), timeout=remaining_time
                    )
                    yield event
                except asyncio.TimeoutError:
                    bound_logger.debug(
                        "Event generator timeout: waiting for event on queue"
                    )
                    stop_event.set()
                except asyncio.CancelledError:
                    bound_logger.debug("Task cancelled")
                    stop_event.set()

            populate_task.cancel()  # After stop_event is set

        return EventGeneratorWrapper(
            generator=event_generator(), populate_task=populate_task
        )

    async def _populate_client_queue(
        self, *, wallet: str, topic: str, client_queue: asyncio.Queue
    ) -> NoReturn:
        logger.trace(
            "SSE Manager: start _populate_client_queue for wallet `{}` and topic `{}`",
            wallet,
            topic,
        )
        event_log = []  # to keep track of events already added for this client queue

        while True:
            if topic == WEBHOOK_TOPIC_ALL:
                for topic_key in self.lifo_cache[wallet].keys():
                    event_log = await self._append_to_queue(
                        wallet=wallet,
                        topic=topic_key,
                        client_queue=client_queue,
                        event_log=event_log,
                    )
            else:
                event_log = await self._append_to_queue(
                    wallet=wallet,
                    topic=topic,
                    client_queue=client_queue,
                    event_log=event_log,
                )

            # Sleep for a short duration to allow sufficient release of concurrency locks
            await asyncio.sleep(CLIENT_QUEUE_POLL_PERIOD)

    async def _append_to_queue(
        self, *, wallet: str, topic: str, client_queue: asyncio.Queue, event_log: List
    ) -> List:
        queue_is_read = False
        async with self.cache_locks[wallet][topic]:
            lifo_queue_for_topic = self.lifo_cache[wallet][topic]
            try:
                while True:
                    timestamp, event = lifo_queue_for_topic.get_nowait()
                    queue_is_read = True
                    if (timestamp, event) not in event_log:
                        self._cache_last_accessed[wallet][topic] = datetime.now()
                        event_log += ((timestamp, event),)
                        client_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                # No event on lifo_queue, so we can continue
                pass
            except asyncio.QueueFull:
                # Because we are using `put_nowait`. Should not happen as queue has no max size
                logger.error(
                    "Client Queue is full for wallet {} on topic {}",
                    wallet,
                    topic,
                )

            if queue_is_read:
                # We've consumed from the lifo_queue, so repopulate it before exiting lock:
                lifo_queue, fifo_queue = await _copy_queue(
                    self.fifo_cache[wallet][topic]
                )
                self.fifo_cache[wallet][topic] = fifo_queue
                self.lifo_cache[wallet][topic] = lifo_queue

        return event_log

    async def _cleanup_cache(self) -> NoReturn:
        while True:
            logger.debug("SSE Manager: Running periodic cleanup task")

            try:
                # Iterate over all cache queues
                for wallet in list(self.lifo_cache.keys()):
                    for topic in list(self.lifo_cache[wallet].keys()):
                        if datetime.now() - self._cache_last_accessed[wallet][
                            topic
                        ] > timedelta(seconds=MAX_EVENT_AGE_SECONDS):
                            async with self.cache_locks[wallet][topic]:
                                del self.lifo_cache[wallet][topic]
                                del self._cache_last_accessed[wallet][topic]

                                if topic in self.fifo_cache[wallet]:
                                    # We are using keys from lifo_cache, so key exists
                                    # should be checked before trying to access in fifo_cache
                                    del self.fifo_cache[wallet][topic]
                                else:
                                    logger.warning(
                                        "SSE Manager: Avoided KeyError in `_cleanup_cache`. "
                                        "fifo_cache keys are not synced with lifo_cache keys, "
                                        "for wallet `{}` and topic `{}`. Maybe caused by client disconnects.",
                                        wallet,
                                        topic,
                                    )

                            del self.cache_locks[wallet][topic]
            except KeyError as e:
                logger.warning(
                    "SSE Manager: Caught KeyError in `_cleanup_cache`: {}.", e
                )

            logger.debug("SSE Manager: Finished cleanup task.")

            # Wait for a while between cleanup operations
            await asyncio.sleep(QUEUE_CLEANUP_PERIOD)


async def _copy_queue(
    queue: asyncio.Queue, maxsize: int = MAX_QUEUE_SIZE
) -> Tuple[asyncio.LifoQueue, asyncio.Queue]:
    # Consuming a queue removes its content. Therefore, we create two new queues to copy one
    logger.trace("SSE Manager: Repopulating cache")
    lifo_queue, fifo_queue = asyncio.LifoQueue(maxsize), asyncio.Queue(maxsize)
    while True:
        try:
            timestamp, item = queue.get_nowait()
            if (
                time.time() - timestamp <= MAX_EVENT_AGE_SECONDS
            ):  # only copy events that are less than our max event age
                await lifo_queue.put((timestamp, item))
                await fifo_queue.put((timestamp, item))
        except asyncio.QueueEmpty:
            break
    logger.trace("SSE Manager: Finished repopulating cache.")

    return lifo_queue, fifo_queue
