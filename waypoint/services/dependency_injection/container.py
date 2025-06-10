from dependency_injector import containers, providers

from shared.services.nats_jetstream import init_nats_client
from waypoint.services.nats_service import NatsEventsProcessor


class Container(containers.DeclarativeContainer):
    """Dependency injection container for the waypoint service."""

    jetstream = providers.Resource(init_nats_client)

    nats_events_processor = providers.Singleton(
        NatsEventsProcessor,
        jetstream=jetstream,
    )
