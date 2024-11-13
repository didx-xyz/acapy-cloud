import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import orjson
from nats.errors import BadSubscriptionError, Error, TimeoutError
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext

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
        self, *, group_id: str, wallet_id: str, topic: str, state: str, look_back: int
    ) -> JetStreamContext.PullSubscription:
        try:
            logger.trace(
                "Subscribing to JetStream for wallet_id: {}, group_id: {}",
                wallet_id,
                group_id,
            )
            group_id = group_id or "*"
            subscribe_kwargs = {
                "subject": f"{NATS_STATE_SUBJECT}.{group_id}.{wallet_id}.{topic}.{state}",
                "stream": NATS_STATE_STREAM,
            }

            # Get the current time in UTC
            current_time = datetime.now(timezone.utc)

            # Subtract look_back time from the current time
            look_back_time = current_time - timedelta(seconds=look_back)

            # Format the time in the required format
            start_time = look_back_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            config = ConsumerConfig(
                deliver_policy=DeliverPolicy.BY_START_TIME,
                opt_start_time=start_time,
            )
            subscription = await self.js_context.pull_subscribe(
                config=config, **subscribe_kwargs
            )

            return subscription

        except BadSubscriptionError as e:
            logger.error("BadSubscriptionError subscribing to NATS: {}", e)
            raise
        except Error as e:
            logger.error("Error subscribing to NATS: {}", e)
            raise
        except Exception:
            logger.exception("Unknown error subscribing to NATS")
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
        logger.debug(
            "Processing events for group {} and wallet {} on topic {} with state {}",
            group_id,
            wallet_id,
            topic,
            state,
        )

        subscription = await self._subscribe(
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            state=state,
            look_back=look_back,
        )

        async def event_generator():
            end_time = time.time() + duration
            while not stop_event.is_set():
                remaining_time = end_time - time.time()
                logger.trace("remaining_time: {}", remaining_time)
                if remaining_time <= 0:
                    logger.debug("Timeout reached")
                    stop_event.set()
                    break

                try:
                    messages = await subscription.fetch(batch=5, timeout=0.2)
                    for message in messages:
                        event = orjson.loads(message.data)
                        yield CloudApiWebhookEventGeneric(**event)
                        await message.ack()
                except TimeoutError:
                    logger.trace("Timeout fetching messages continuing...")
                    await asyncio.sleep(0.1)

        try:
            yield event_generator()
        except asyncio.CancelledError:
            logger.debug("Event generator cancelled")
            stop_event.set()
        finally:
            logger.trace("Closing subscription...")
            await subscription.unsubscribe()
            logger.debug("Subscription closed")

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
