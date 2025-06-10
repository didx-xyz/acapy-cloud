import asyncio
from typing import List, NoReturn

from aries_cloudcontroller import AcaPyClient
from nats.errors import BadSubscriptionError, Error
from nats.js.client import JetStreamContext
from nats.js.errors import FetchTimeoutError
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_never,
    wait_fixed,
)

from endorser.util.endorsement import accept_endorsement, should_accept_endorsement
from shared.constants import (
    ENDORSER_DURABLE_CONSUMER,
    GOVERNANCE_AGENT_API_KEY,
    GOVERNANCE_AGENT_URL,
    GOVERNANCE_LABEL,
    NATS_STREAM,
    NATS_SUBJECT,
)
from shared.log_config import get_logger
from shared.models.endorsement import Endorsement
from shared.models.webhook_events.payloads import CloudApiWebhookEventGeneric
from shared.util.rich_parsing import parse_json_with_error_handling

logger = get_logger(__name__)


class EndorsementProcessor:
    """
    Class to process endorsement webhook events that Benthos acapy-events-processor writes to `endorser_nats_subject`
    """

    def __init__(self, jetstream: JetStreamContext) -> None:
        self.jetstream: JetStreamContext = jetstream

        self.endorser_nats_subject = f"{NATS_SUBJECT}.endorser.*"

        self._tasks: List[asyncio.Task] = []  # To keep track of running tasks

    def start(self) -> None:
        """
        Starts the background tasks for processing endorsement events.
        """
        self._tasks.append(
            asyncio.create_task(
                self._process_endorsement_requests(), name="Process endorsements"
            )
        )

        logger.info("Endorsement processing started.")

    async def stop(self) -> None:
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

        logger.info("Endorsement processing stopped.")

    def are_tasks_running(self) -> bool:
        """
        Checks if the background tasks are still running.

        Returns:
            True if all background tasks are running, False if any task has stopped.
        """
        logger.trace("Checking if all tasks are running")

        tasks_running = self._tasks and all(not task.done() for task in self._tasks)

        if not tasks_running:
            for task in self._tasks:
                if task.done():
                    logger.error("Task `{}` is not running", task.get_name())

        all_running = tasks_running

        logger.trace("All tasks running: {}", all_running)
        return all_running

    async def _process_endorsement_requests(self) -> NoReturn:
        subscription = await self._subscribe()
        while True:
            try:
                logger.trace(
                    "Fetching messages from NATS subject: {}",
                    self.endorser_nats_subject,
                )
                messages = await subscription.fetch(batch=1, timeout=0.5, heartbeat=0.2)
                for message in messages:
                    message_subject = message.subject
                    message_data = message.data.decode()
                    logger.debug(
                        "Received message: {}, with subject {}",
                        message_data,
                        message_subject,
                    )
                    try:
                        await self._process_endorsement_event(message_data)
                    except Exception as e:  # pylint: disable=W0703
                        logger.error("Error processing endorsement event: {}", e)
                        await self._handle_unprocessable_endorse_event(
                            message_subject, message_data, e
                        )
                    finally:
                        await message.ack()
            except FetchTimeoutError:
                logger.trace("Encountered FetchTimeoutError. Continuing ...")
                await asyncio.sleep(0.1)
            except TimeoutError as e:
                logger.warning("Timeout fetching messages: {}. Re-subscribing.", e)
                await subscription.unsubscribe()
                subscription = await self._subscribe()
            except Exception:  # pylint: disable=W0718
                logger.exception("Unexpected error in endorsement processing loop")
                await asyncio.sleep(2)

    async def _process_endorsement_event(self, event_json: str) -> None:
        """
        Processes an individual endorsement event, evaluating if it should be accepted and then endorsing as governance

        Args:
            event_json: The JSON string representation of the endorsement event.
        """
        event = parse_json_with_error_handling(
            CloudApiWebhookEventGeneric, event_json, logger
        )
        logger.debug("Processing endorsement event for agent `{}`", event.origin)

        # We're only interested in events from the governance agent
        if event.wallet_id != GOVERNANCE_LABEL:
            logger.warning("Endorsement request is not for governance agent.")
            return

        endorsement = Endorsement(**event.payload)
        transaction_id = endorsement.transaction_id

        async with AcaPyClient(
            base_url=GOVERNANCE_AGENT_URL, api_key=GOVERNANCE_AGENT_API_KEY
        ) as client:
            # Check if endorsement request is indeed applicable
            transaction = await should_accept_endorsement(client, transaction_id)
            if not transaction:
                logger.info(  # The check has already logged the reason as warning
                    "Endorsement request with transaction id `{}` is not applicable for endorsement.",
                    transaction_id,
                )
                return

            logger.info(
                "Endorsement request is applicable for endorsement: {}",
                transaction.model_dump(exclude={"messages_attach"}),
            )
            await accept_endorsement(client, transaction_id)

    async def _handle_unprocessable_endorse_event(
        self, key: str, event_json: str, error: Exception
    ) -> None:
        """
        Handles an event that could not be processed successfully. The unprocessable event is persisted
        to a separate key for further investigation.

        Args:
            key: The Nats subject key where the problematic event was found.
            error: The exception that occurred during event processing.
        """
        bound_logger = logger.bind(body={"key": key})
        bound_logger.warning("Handling problematic endorsement event")

        unprocessable_key = f"unprocessable.{key}"
        error_message = f"Could not process: {event_json}. Error: {error}"

        bound_logger.info(
            "Saving record of problematic event at key: {}. Error: `{}`",
            unprocessable_key,
            error_message,
        )
        await self.jetstream.publish(unprocessable_key, error_message.encode())
        bound_logger.info("Successfully handled unprocessable event.")

    async def _subscribe(self) -> JetStreamContext.PullSubscription:
        """
        Subscribes to the NATS subject for endorsement events.
        """
        subscribe_kwargs = {
            "subject": self.endorser_nats_subject,
            "durable": ENDORSER_DURABLE_CONSUMER,
            "stream": NATS_STREAM,
        }

        logger.info("Subscribing to NATS: {}", subscribe_kwargs)

        @retry(
            retry=retry_if_exception_type(TimeoutError),
            wait=wait_fixed(1),
            stop=stop_never,
            after=self._retry_log,
        )
        async def pull_subscribe(**kwargs):
            try:
                subscription = await self.jetstream.pull_subscribe(**kwargs)
                logger.debug("Subscribed to NATS subject")
                return subscription
            except (BadSubscriptionError, Error) as e:
                logger.error("Error subscribing to NATS subject: {}", e)
                raise e
            except Exception:  # pylint: disable=W0703
                logger.exception("Unknown error subscribing to NATS subject")
                raise

        try:
            return await pull_subscribe(**subscribe_kwargs)
        except Exception:  # pylint: disable=W0703
            logger.exception("Error subscribing to NATS subject")
            raise

    def _retry_log(self, retry_state: RetryCallState):
        """Custom logging for retry attempts."""
        if retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            logger.warning(
                "Retry attempt {} failed due to {}: {}",
                retry_state.attempt_number,
                type(exception).__name__,
                exception,
            )

    async def check_jetstream(self):
        try:
            account_info = await self.jetstream.account_info()
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
