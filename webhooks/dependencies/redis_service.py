from typing import AsyncIterator, List

import aioredis
from aioredis import Redis

from shared.log_config import get_logger

logger = get_logger(__name__)


async def init_redis_pool(host: str, password: str) -> AsyncIterator[Redis]:
    pool = await aioredis.from_url(f"redis://{host}", password=password)
    yield pool
    pool.close()
    await pool.wait_closed()


class RedisService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def add_wallet_entry(self, wallet_id: str, event_json: str) -> None:
        bound_logger = logger.bind(body={"wallet_id": wallet_id, "event": event_json})
        bound_logger.debug("Write entry to redis")
        await self._redis.sadd(wallet_id, event_json)
        bound_logger.debug("Successfully wrote entry to redis.")

    async def get_json_webhook_events_by_wallet(self, wallet_id: str) -> List[str]:
        bound_logger = logger.bind(body={"wallet_id": wallet_id})
        bound_logger.debug("Fetching entries from redis by wallet id")
        entries: List[str] = await self._redis.smembers(wallet_id)
        bound_logger.debug("Successfully fetched redis entries.")
        return entries

    async def get_json_webhook_events_by_wallet_and_topic(
        self, wallet_id: str, topic: str
    ) -> List[str]:
        entries = await self.get_json_webhook_events_by_wallet(wallet_id)
        # Filter the json entry for our requested topic without deserialising
        topic_str = f'"topic":"{topic}"'
        return [entry for entry in entries if topic_str in entry]
