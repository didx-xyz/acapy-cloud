import asyncio
import time
from datetime import datetime
from logging import Logger
from typing import List, Union

import orjson
import xxhash
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
    wallet_label: str
    created_at: str
    updated_at: str


class Event(BaseModel):
    """Base class for all events"""

    subject: str
    payload: Union[TenantEventPayload, SchemaEventPayload]


class EventFactory:
    """Factory for creating events"""

    @staticmethod
    def create_tenant_event(
        subject: str,
        wallet_id: str,
        wallet_label: str,
        wallet_name: str,
        roles: List[str],
        state: str,
        group_id: str,
        topic: str,
        image_url: str = "",
        created_at: str = None,
        updated_at: str = None,
    ) -> Event:
        """Create a tenant event"""
        if created_at is None:
            created_at = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        if updated_at is None:
            updated_at = created_at

        payload = TenantEventPayload(
            wallet_id=wallet_id,
            wallet_label=wallet_label,
            wallet_name=wallet_name,
            roles=roles,
            topic=topic,
            state=state,
            group_id=group_id,
            image_url=image_url,
            created_at=created_at,
            updated_at=updated_at,
        )
        return Event(subject=subject, payload=payload)

    @staticmethod
    def create_schema_event(
        subject: str,
        schema_id: str,
        name: str,
        version: str,
        attributes: List[str],
        wallet_label: str,
        state: str,
        topic: str,
        created_at: str = None,
        updated_at: str = None,
    ) -> Event:
        """Create a schema event"""
        if created_at is None:
            created_at = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        if updated_at is None:
            updated_at = created_at

        payload = SchemaEventPayload(
            schema_id=schema_id,
            name=name,
            version=version,
            attributes=attributes,
            wallet_label=wallet_label,
            topic=topic,
            state=state,
            created_at=created_at,
            updated_at=updated_at,
        )
        return Event(subject=subject, payload=payload)


class NatsJetstreamPublish:
    """
    Publish messages to NATS JetStream.
    """

    def __init__(self, jetstream: JetStreamContext):
        self.js_context = jetstream

    async def publish(
        self, logger: Logger, event: Event, retries: int = 3, delay: int = 5
    ) -> None:
        """
        Publish a message to a NATS JetStream subject.
        """
        attempt = 0
        payload_dict = event.payload.model_dump()
        dict_bytes = orjson.dumps(payload_dict)
        hashed_payload = xxhash.xxh64(dict_bytes).intdigest()

        while attempt < retries:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Nats-Msg-Id": str(hashed_payload),
                    "event_origin": (
                        event.payload.wallet_label
                        if hasattr(event.payload, "wallet_label")
                        else None
                    ),
                    "event_topic": event.payload.topic,
                    "event_payload_state": event.payload.state,
                    "event_processed_at": str(time.time_ns()),
                    "event_payload_created_at": (
                        self._convert_timestamp(event.payload.created_at)
                    ),
                    "event_payload_updated_at": (
                        self._convert_timestamp(event.payload.updated_at)
                    ),
                }

                ack = await self.js_context.publish(
                    event.subject,
                    dict_bytes,
                    stream="cloudapi_aries_events",
                    headers=headers,
                )

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
            except Exception as e:
                logger.error("Unexpected error: {}", e)
                attempt += 1
                if attempt < retries:
                    await asyncio.sleep(delay)
                else:
                    logger.error("Failed to publish message after {} attempts", retries)
                    raise e

    def _convert_timestamp(self, timestamp: str) -> str:
        """
        Convert a timestamp string to a Unix timestamp in nanoseconds.
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return str(int(dt.timestamp() * 1_000_000))
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {timestamp}") from e
