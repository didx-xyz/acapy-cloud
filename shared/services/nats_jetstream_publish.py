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


class TenantEventPayload(BaseModel):
    """Payload for tenant-related events"""

    wallet_id: str
    wallet_label: str
    wallet_name: str
    roles: List[str]
    image_url: str
    group_id: str
    topic: str
    state: str
    created_at: str
    updated_at: str


class SchemaEventPayload(BaseModel):
    """Payload for schema-related events"""

    schema_id: str
    name: str
    version: str
    attributes: List[str]
    topic: str
    state: str
    created_at: str
    updated_at: str


class Event(BaseModel):
    """Base class for all events"""

    subject: str
    payload: Union[TenantEventPayload, SchemaEventPayload]


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
