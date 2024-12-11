import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import orjson
from nats.errors import BadSubscriptionError, Error, TimeoutError
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext
from nats.js.errors import FetchTimeoutError
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_never,
    wait_exponential,
)

from shared.constants import NATS_STATE_STREAM, NATS_STATE_SUBJECT
from shared.log_config import get_logger
from shared.models.webhook_events import CloudApiWebhookEventGeneric

logger = get_logger(__name__)


class NatsEventsProcessor:
    """
    Class to handle processing of NATS events. Calling the process_events method will
    subscribe to the NATS server and return an async generator that will yield events
    """

    def __init__(self, jetstream: JetStreamContext):
        self.js_context: JetStreamContext = jetstream

    async def _subscribe(
        self,
        *,
        group_id: str,
        wallet_id: str,
        topic: str,
        state: str,
        start_time: str = None,
    ) -> JetStreamContext.PullSubscription:
        bound_logger = logger.bind(
            body={
                "wallet_id": wallet_id,
                "group_id": group_id,
                "topic": topic,
                "state": state,
                "start_time": start_time,
            }
        )

        bound_logger.debug("Subscribing to JetStream")

        group_id = group_id or "*"
        subscribe_kwargs = {
            "subject": f"{NATS_STATE_SUBJECT}.{group_id}.{wallet_id}.{topic}.{state}",
            "stream": NATS_STATE_STREAM,
        }

        config = ConsumerConfig(
            deliver_policy=DeliverPolicy.BY_START_TIME,
            opt_start_time=start_time,
        )

        def _retry_log(retry_state: RetryCallState):
            """Custom logging for retry attempts."""
            if retry_state.outcome.failed:
                exception = retry_state.outcome.exception()
                bound_logger.warning(
                    "Retry attempt {} failed due to {}: {}",
                    retry_state.attempt_number,
                    type(exception).__name__,
                    exception,
                )

        # This is a custom retry decorator that will retry on TimeoutError
        # and wait exponentially up to a max of 16 seconds between retries indefinitely
        @retry(
            retry=retry_if_exception_type(TimeoutError),
            wait=wait_exponential(multiplier=1, max=16),
            after=_retry_log,
            stop=stop_never,
        )
        async def pull_subscribe(config, **kwargs):
            try:
                bound_logger.trace("Attempting to subscribe to JetStream")
                subscription = await self.js_context.pull_subscribe(
                    config=config, **kwargs
                )
                bound_logger.debug("Successfully subscribed to JetStream")
                return subscription
            except BadSubscriptionError as e:
                bound_logger.error("BadSubscriptionError subscribing to NATS: {}", e)
                raise
            except Error as e:
                bound_logger.error("Error subscribing to NATS: {}", e)
                raise

        try:
            return await pull_subscribe(config, **subscribe_kwargs)
        except Exception:
            bound_logger.exception("An exception occurred subscribing to NATS")
            raise

    @asynccontextmanager
    async def process_events(
        self,
        *,
        group_id: str,
        wallet_id: str,
        topic: str,
        state: str,
        stop_event: asyncio.Event,
        duration: int = 10,
        look_back: int = 60,
    ):
        bound_logger = logger.bind(
            body={
                "wallet_id": wallet_id,
                "group_id": group_id,
                "topic": topic,
                "state": state,
                "duration": duration,
                "look_back": look_back,
            }
        )
        bound_logger.debug("Processing events")
        # Get the current time in UTC
        current_time = datetime.now(timezone.utc)

        # Subtract look_back time from the current time
        look_back_time = current_time - timedelta(seconds=look_back)

        # Format the time in the required format
        start_time = look_back_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        async def event_generator(
            *,
            subscription: JetStreamContext.PullSubscription,
            group_id: str,
            wallet_id: str,
            topic: str,
            state: str,
            stop_event: asyncio.Event,
        ):
            try:
                end_time = time.time() + duration
                while not stop_event.is_set():
                    remaining_time = end_time - time.time()
                    bound_logger.trace("Remaining time: {}", remaining_time)
                    if remaining_time <= 0:
                        bound_logger.debug("Timeout reached")
                        stop_event.set()
                        break

                    try:
                        messages = await subscription.fetch(
                            batch=5, timeout=0.5, heartbeat=0.2
                        )
                        for message in messages:
                            event = orjson.loads(message.data)
                            bound_logger.trace("Received event: {}", event)
                            yield CloudApiWebhookEventGeneric(**event)
                            await message.ack()

                    except FetchTimeoutError:
                        # Fetch timeout, continue
                        bound_logger.trace("Timeout fetching messages continuing...")
                        await asyncio.sleep(0.1)

                    except TimeoutError:
                        # Timeout error, resubscribe
                        bound_logger.warning(
                            "Subscription lost connection, attempting to resubscribe..."
                        )
                        try:
                            await subscription.unsubscribe()
                        except BadSubscriptionError as e:
                            # If we can't unsubscribe, log the error and continue
                            bound_logger.warning(
                                "BadSubscriptionError unsubscribing from NATS: {}", e
                            )

                        subscription = await self._subscribe(
                            group_id=group_id,
                            wallet_id=wallet_id,
                            topic=topic,
                            state=state,
                            start_time=start_time,
                        )
                        bound_logger.debug("Successfully resubscribed to NATS.")

                    except Exception:  # pylint: disable=W0718
                        bound_logger.exception("Unexpected error in event generator")
                        stop_event.set()
                        raise

            except asyncio.CancelledError:
                bound_logger.debug("Event generator cancelled")
                stop_event.set()

        try:
            subscription = await self._subscribe(
                group_id=group_id,
                wallet_id=wallet_id,
                topic=topic,
                state=state,
                start_time=start_time,
            )
            yield event_generator(
                subscription=subscription,
                stop_event=stop_event,
                group_id=group_id,
                wallet_id=wallet_id,
                topic=topic,
                state=state,
            )
        except Exception as e:  # pylint: disable=W0718
            bound_logger.exception("Unexpected error processing events: {}")
            raise e

        finally:
            if subscription:
                try:
                    bound_logger.trace("Closing subscription...")
                    await subscription.unsubscribe()
                    bound_logger.debug("Subscription closed")
                except BadSubscriptionError as e:
                    bound_logger.warning(
                        "BadSubscriptionError unsubscribing from NATS: {}", e
                    )

    async def check_jetstream(self):
        try:
            account_info = await self.js_context.account_info()
            is_working = account_info.streams > 0
            logger.trace("JetStream check completed. Is working: {}", is_working)
            return {
                "is_working": is_working,
                "streams_count": account_info.streams,
                "consumers_count": account_info.consumers,
            }
        except Exception:  # pylint: disable=W0718
            logger.exception("Caught exception while checking jetstream status")
            return {"is_working": False}
