from typing import Any, Dict

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Request, status
from fastapi_websocket_pubsub import PubSubEndpoint

from shared import APIRouter
from shared.log_config import get_logger
from shared.models.topics import WEBHOOK_TOPIC_ALL, RedisItem, TopicItem, topic_mapping
from webhooks.dependencies.container import Container
from webhooks.dependencies.redis_service import RedisService
from webhooks.dependencies.sse_manager import SseManager

logger = get_logger(__name__)

router = APIRouter()

endpoint = PubSubEndpoint()
endpoint.register_route(router, "/pubsub")


# 'origin' helps to distinguish where a hook is from
# eg the admin, tenant or OP agent respectively
@router.post(
    "/{origin}/topic/{acapy_topic}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Receive webhook events from ACA-Py",
)
@inject
async def topic_root(
    acapy_topic: str,
    origin: str,
    body: Dict[str, Any],
    request: Request,
    redis_service: RedisService = Depends(Provide[Container.redis_service]),
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    bound_logger = logger.bind(
        body={"acapy_topic": acapy_topic, "origin": origin, "body": body}
    )
    bound_logger.debug("Handling received event")
    try:
        wallet_id = request.headers["x-wallet-id"]
    except KeyError:
        wallet_id = "admin"  # todo: defaults to admin ...
    # FIXME: wallet_id is admin for all admin wallets from different origins. We should make a difference on this
    # Maybe the wallet id should be the role (governance, tenant-admin)?

    # We need to map from the acapy webhook topic to a unified cloud api topic. If the topic doesn't exist in the topic
    # mapping it means we don't support the webhook event yet and we will ignore it for now. This allows us to add more
    # webhook events as needed, without needing to break any models
    topic = topic_mapping.get(acapy_topic)
    if not topic:
        bound_logger.warning(
            "Not publishing webhook event for acapy_topic `{}` as it doesn't exist in the topic_mapping",
            acapy_topic,
        )
        return

    redis_item: RedisItem = RedisItem(
        payload=body,
        origin=origin,
        topic=topic,
        acapy_topic=acapy_topic,
        wallet_id=wallet_id,
    )

    webhook_event: TopicItem = redis_service.transform_topic_entry(redis_item)
    if not webhook_event:
        bound_logger.warning(
            "Not publishing webhook event for topic `{}` as no transformer exists for the topic",
            topic,
        )
        return

    # Enqueue the event for SSE
    await sse_manager.enqueue_sse_event(webhook_event)

    # publish the webhook to subscribers for the following topics
    #  - current wallet id
    #  - topic of the event
    #  - topic and wallet id combined as topic-wallet_id
    #    - this allows for fine grained subscriptions (i.e. the endorser service)
    #  - 'all' topic, which allows to subscribe to all published events
    await endpoint.publish(
        topics=[
            topic,
            wallet_id,
            f"{topic}-{wallet_id}",
            WEBHOOK_TOPIC_ALL,
        ],
        data=webhook_event.model_dump_json(),
    )

    # Add data to redis
    await redis_service.add_wallet_entry(redis_item)

    logger.debug("Successfully processed received webhook.")
