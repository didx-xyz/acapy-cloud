import asyncio
from logging import Logger

import orjson
from nats.errors import (
    AuthorizationError,
    ConnectionClosedError,
    NoServersError,
    TimeoutError,
    UnexpectedEOF,
)
from nats.js.client import JetStreamContext
from pydantic import BaseModel


class BaseEvent(BaseModel):
    """
    Base class for events.
    """

    subject: str
    data: dict


class TenantEvent(BaseEvent):
    """
    Event for tenant-related actions.
    """
    pass # TODO: Add specific fields and methods for tenant events

class SchemaEvent(BaseEvent):
    """
    Event for schema-related actions.
    """
    pass # TODO: Add specific fields and methods for schema events



class NatsJetstreamPublish:
    """
    Publish messages to NATS JetStream.
    """

    def __init__(self, jetstream: JetStreamContext):
        self.js_context = jetstream

    async def publish(
        self, logger: Logger, event: BaseEvent, retries: int = 3, delay: int = 5
    ) -> None:
        """
        Publish a message to a NATS JetStream subject.
        """
        attempt = 0
        dict_bytes = orjson.dumps(event.data)
        while attempt < retries:
            try:

                ack = await self.js_context.publish(event.subject, dict_bytes)

                if ack.duplicate:
                    logger.warning("Duplicate message detected: {}", ack)
                else:
                    logger.debug("Message published: {}", ack)
                return

            except (
                AuthorizationError,
                ConnectionClosedError,
                NoServersError,
                TimeoutError,
                UnexpectedEOF,
            ) as e:
                logger.error("NATS connection error: {}", e)
                attempt += 1
                if attempt < retries:
                    await asyncio.sleep(delay)
                else:
                    logger.error("Failed to publish message after {} attempts", retries)
                    raise e
