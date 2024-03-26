import asyncio
import sys
import time
from collections import defaultdict as ddict
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, NoReturn, Tuple

from pydantic import ValidationError
from redis import ConnectionError

from shared.constants import (
    CLIENT_QUEUE_POLL_PERIOD,
    MAX_EVENT_AGE_SECONDS,
    MAX_QUEUE_SIZE,
    QUEUE_CLEANUP_PERIOD,
)
from shared.log_config import get_logger
from shared.models.webhook_events import WEBHOOK_TOPIC_ALL, CloudApiWebhookEventGeneric
from webhooks.services.webhooks_redis_serivce import WebhooksRedisService
from webhooks.util.event_generator_wrapper import EventGeneratorWrapper
from webhooks.web.routers.websocket import publish_event_on_websocket

logger = get_logger(__name__)


class SseManager:
    """
    Class to manage Server-Sent Events (SSE).
    """

    def __init__(self, redis_service: WebhooksRedisService) -> None:
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

        self._pubsub = None  # for managing redis pubsub connection

        self._tasks: List[asyncio.Task] = []  # To keep track of running tasks

    def start(self):
        """
        Start the background tasks as part of SseManager's lifecycle
        """
        logger.info("Starting SSE Manager background tasks")
        # backfill previous events from redis, if any
        asyncio.create_task(self._backfill_events(), name="Backfill events")

        # listen for new events on redis pubsub channel
        self._tasks.append(
            asyncio.create_task(
                self._listen_for_new_events(), name="Listen for new events"
            )
        )

        # process incoming events and cleanup queues
        self._tasks.append(
            asyncio.create_task(
                self._process_incoming_events(), name="Process incoming events"
            )
        )
        self._tasks.append(
            asyncio.create_task(self._cleanup_cache(), name="Cleanup cache")
        )
        logger.info("SSE Manager background tasks started")

    async def stop(self):
        """
        Stops all background tasks gracefully.
        """
        for task in self._tasks:
            task.cancel()  # Request cancellation of the task
            try:
                await task  # Wait for the task to be cancelled
            except asyncio.CancelledError:
                pass  # Expected error upon cancellation, can be ignored
        self._tasks.clear()  # Clear the list of tasks
        logger.info("SSE Manager processes stopped.")

        if self._pubsub:
            self._pubsub.disconnect()
            logger.info("Disconnected SseManager pubsub instance")

    def are_tasks_running(self) -> bool:
        """
        Checks if the background tasks are still running.

        Returns:
            True if all background tasks are running, False if any task has stopped.
        """
        logger.debug("Checking if all tasks are running")

        if not self._pubsub:
            logger.error("Pubsub is not running")

        all_running = self._tasks and all(not task.done() for task in self._tasks)
        logger.debug("All tasks running: {}", all_running)

        if not all_running:
            for task in self._tasks:
                if task.done():
                    logger.warning("Task `{}` is not running", task.get_name())
        return self._pubsub and all_running

    async def _listen_for_new_events(
        self, max_retries=5, retry_duration=0.33
    ) -> NoReturn:
        """
        Listen on redis pubsub channel for new SSE events; read the event and add to queue.
        Terminates after exceeding max_retries connection attempts.
        """
        retry_count = 0
        sleep_duration = 0.1  # time to sleep after empty pubsub message

        while retry_count < max_retries:
            try:
                logger.info("Creating pubsub instance")
                self._pubsub = self.redis_service.redis.pubsub()

                logger.info("Subscribing to pubsub instance for SSE events")
                self._pubsub.subscribe(self.redis_service.sse_event_pubsub_channel)

                # Reset retry_count upon successful connection
                retry_count = 0

                logger.info("Begin SSE processing pubsub messages")
                while True:
                    message = self._pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        logger.debug("Got pubsub message: {}", message)
                        await self._process_redis_event(message)
                    else:
                        logger.trace("message is empty, retry in {}s", sleep_duration)
                        await asyncio.sleep(sleep_duration)  # Prevent a busy loop
            except ConnectionError as e:
                logger.error("ConnectionError detected: {}.", e)
            except Exception:  # General exception catch
                logger.exception("Unexpected error.")

            retry_count += 1
            logger.warning(
                "Attempt #{} to reconnect in {}s ...", retry_count, retry_duration
            )
            await asyncio.sleep(retry_duration)  # Wait a bit before retrying

        # If the loop exits due to retry limit exceeded
        logger.critical(
            "Failed to connect to Redis after {} attempts. Terminating service.",
            max_retries,
        )
        sys.exit(1)  # todo: Not graceful

    async def _process_redis_event(self, message: Dict[str, Any]) -> None:
        try:
            message_data = message["data"]
            if isinstance(message_data, bytes):
                message_data = message_data.decode("utf-8")

            group_id, wallet_id, timestamp_ns_str = message_data.split(":")
            timestamp_ns = int(timestamp_ns_str)

            # Fetch the event with the exact timestamp from the sorted set
            json_events = self.redis_service.get_json_cloudapi_events_by_timestamp(
                group_id=group_id,
                wallet_id=wallet_id,
                start_timestamp=timestamp_ns,
                end_timestamp=timestamp_ns,
            )

            for json_event in json_events:
                try:
                    parsed_event = CloudApiWebhookEventGeneric.model_validate_json(
                        json_event
                    )
                    topic = parsed_event.topic

                    # Add event to SSE queue for processing
                    logger.trace("Put parsed event on events queue: {}", parsed_event)
                    await self.incoming_events.put(parsed_event)

                    # Also publish event to websocket
                    # Doing it here makes websockets stateless as well
                    await publish_event_on_websocket(
                        event_json=json_event,
                        group_id=group_id,
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

    async def _backfill_events(self) -> None:
        """
        Backfill events from Redis that were published within the MAX_EVENT_AGE window.
        """
        logger.info("Start backfilling SSE queue with recent events from redis")
        try:
            # Calculate the minimum timestamp for backfilling
            current_time_ns = time.time_ns()  # Current time in nanoseconds
            min_timestamp_ns = current_time_ns - (MAX_EVENT_AGE_SECONDS * 1e9)
            logger.debug("Backfilling events from timestamp_ns: {}", min_timestamp_ns)

            # Get all wallets to backfill events for
            wallets = self.redis_service.get_all_cloudapi_wallet_ids()

            total_events_backfilled = 0
            for wallet_id in wallets:
                # Fetch events within the time window from Redis for each wallet
                events = self.redis_service.get_cloudapi_events_by_timestamp(
                    wallet_id, min_timestamp_ns, "+inf"
                )

                # Enqueue the fetched events
                for event in events:
                    await self.incoming_events.put(event)
                    total_events_backfilled += 1

            logger.info("Backfilled a total of {} events.", total_events_backfilled)
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

                timestamped_event: Tuple(float, CloudApiWebhookEventGeneric) = (  # type: ignore
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
        lookback_time: int = MAX_EVENT_AGE_SECONDS,
        duration: int = 0,
    ) -> EventGeneratorWrapper:
        """
        Create a SSE stream of events for a wallet_id on a specific topic

        Args:
            wallet: The ID of the wallet subscribing to the topic.
            topic: The topic for which to create the event stream.
            stop_event: An asyncio.Event to signal a stop request
            lookback_time: Duration (s) to look back for older events. 0 means from now
            duration: Timeout duration in seconds. 0 means no timeout.
        """
        client_queue = asyncio.Queue()

        populate_task = asyncio.create_task(
            self._populate_client_queue(
                wallet=wallet,
                topic=topic,
                client_queue=client_queue,
                lookback_time=lookback_time,
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
        self,
        *,
        wallet: str,
        topic: str,
        client_queue: asyncio.Queue,
        lookback_time: int = MAX_EVENT_AGE_SECONDS,
    ) -> NoReturn:
        logger.trace(
            "SSE Manager: start _populate_client_queue for wallet `{}` and topic `{}`",
            wallet,
            topic,
        )
        event_log = []  # to keep track of events already added for this client queue

        now = time.time()
        since_timestamp = now - lookback_time
        while True:
            if topic == WEBHOOK_TOPIC_ALL:
                for topic_key in self.lifo_cache[wallet].keys():
                    event_log = await self._append_to_queue(
                        wallet=wallet,
                        topic=topic_key,
                        client_queue=client_queue,
                        event_log=event_log,
                        since_timestamp=since_timestamp,
                    )
            else:
                event_log = await self._append_to_queue(
                    wallet=wallet,
                    topic=topic,
                    client_queue=client_queue,
                    event_log=event_log,
                    since_timestamp=since_timestamp,
                )

            # Sleep for a short duration to allow sufficient release of concurrency locks
            await asyncio.sleep(CLIENT_QUEUE_POLL_PERIOD)

    async def _append_to_queue(
        self,
        *,
        wallet: str,
        topic: str,
        client_queue: asyncio.Queue,
        event_log: List,
        since_timestamp: float = 0,
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
                        if timestamp >= since_timestamp:
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

    async def check_wallet_belongs_to_group(
        self, wallet_id: str, group_id: str, max_checks: int = 10, delay: float = 0.1
    ) -> bool:
        # We offer some grace window, in case SSE connection is attempted before any webhooks exist
        # So we will retry checking `max_checks` times, with `delay` sleep in between
        valid_wallet_group = False
        attempt = 1
        while not valid_wallet_group and attempt <= max_checks:
            valid_wallet_group = self.redis_service.check_wallet_belongs_to_group(
                wallet_id=wallet_id, group_id=group_id
            )
            if not valid_wallet_group:
                attempt += 1
                await asyncio.sleep(delay)

        return valid_wallet_group


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
