from typing import List

from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from shared import APIRouter
from shared.log_config import get_logger
from shared.models.webhook_events import CloudApiWebhookEventGeneric
from webhooks.services.dependency_injection.container import Container
from webhooks.services.webhooks_redis_service import WebhooksRedisService

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks")


@router.get(
    "/{wallet_id}",
    summary="Get 100 most recent webhook events for a wallet ID",
    response_model=List[CloudApiWebhookEventGeneric],
)
@inject
async def get_webhooks_by_wallet(
    wallet_id: str,
    redis_service: WebhooksRedisService = Depends(Provide[Container.redis_service]),
) -> List[CloudApiWebhookEventGeneric]:
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.info("GET request received: Fetch all webhook events for wallet")

    data = redis_service.get_cloudapi_events_by_wallet(wallet_id, num=100)

    if data:
        bound_logger.info("Successfully fetched webhooks events for wallet.")
    else:
        bound_logger.info("No webhooks events returned for wallet.")
    return data


@router.get(
    "/{wallet_id}/{topic}",
    summary="Get 100 most recent webhook events for a wallet ID and topic pair",
    response_model=List[CloudApiWebhookEventGeneric],
)
@inject
async def get_webhooks_by_wallet_and_topic(
    wallet_id: str,
    topic: str,
    redis_service: WebhooksRedisService = Depends(Provide[Container.redis_service]),
) -> List[CloudApiWebhookEventGeneric]:
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "topic": topic})
    bound_logger.info(
        "GET request received: Fetch all webhook events for wallet and topic"
    )

    data = redis_service.get_cloudapi_events_by_wallet_and_topic(
        wallet_id=wallet_id, topic=topic, num=100
    )

    if data:
        bound_logger.info("Successfully fetched webhooks events for wallet and topic.")
    else:
        bound_logger.info("No webhooks events returned for wallet and topic pair.")
    return data
