from dependency_injector import containers, providers

from webhooks.dependencies import redis_service
from webhooks.dependencies.sse_manager import SseManager


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    redis_pool = providers.Resource(
        redis_service.init_redis_pool,
        host=config.redis_host,
        password=config.redis_password,
    )
    redis_service = providers.Singleton(
        redis_service.RedisService,
        redis=redis_pool,
    )
    sse_manager = providers.Singleton(SseManager)


def get_container():
    configured_container = Container()
    configured_container.config.redis_host.from_env("REDIS_HOST", "localhost")
    configured_container.config.redis_password.from_env("REDIS_PASSWORD", "")
    return configured_container
