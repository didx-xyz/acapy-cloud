from typing import Any

from pydantic import BaseModel


class WebhookEvent(BaseModel):
    wallet_id: str
    topic: str
    origin: str
    group_id: str | None = None


# When reading json webhook events from NATS and deserializing back into a CloudApiWebhookEvent,
# it does not always parse to the correct WebhookEventPayloadType for the payload.
# So, use the generic version when parsing NATS events
class CloudApiWebhookEventGeneric(WebhookEvent):
    payload: dict[str, Any]
