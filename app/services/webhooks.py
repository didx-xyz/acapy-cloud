from typing import List

from httpx import HTTPError

from shared import WEBHOOKS_URL
from shared.log_config import get_logger
from shared.models.webhook_events import CloudApiTopics
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


async def get_hooks_for_wallet(wallet_id: str) -> List:
    """
    Gets webhooks for wallet. Only return the first 100 hooks to not overload OpenAPI interface
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.info("Fetching webhooks events from /webhooks/wallet_id")
    try:
        async with RichAsyncClient() as client:
            hooks = (await client.get(f"{WEBHOOKS_URL}/webhooks/{wallet_id}")).json()
            return hooks if hooks else []
    except HTTPError as e:
        bound_logger.error("HTTP Error caught when fetching webhooks: {}.", e)
        raise e


async def get_hooks_for_wallet_by_topic(wallet_id: str, topic: CloudApiTopics) -> List:
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "topic": topic})
    bound_logger.info("Fetching webhooks events from /webhooks/wallet_id/topic")
    try:
        async with RichAsyncClient() as client:
            hooks = (
                await client.get(f"{WEBHOOKS_URL}/webhooks/{wallet_id}/{topic}")
            ).json()
            return hooks if hooks else []
    except HTTPError as e:
        bound_logger.error("HTTP Error caught when fetching webhooks: {}.", e)
        raise e
