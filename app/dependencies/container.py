from dependency_injector import containers, providers

from shared.services.nats_jetstream import init_nats_client
from shared.services.nats_jetstream_publish import NatsJetstreamPublish


class Container(containers.DeclarativeContainer):
    """
    Dependency injection container for the api endpoints.

    This container is responsible for creating and managing the lifecycle of
    the NATS Jetstream and custom publisher
    """

    jetstream = providers.Resource(init_nats_client)

    # Singleton provider for the NATS Jetstream publisher
    nats_jetstream_publisher = providers.Singleton(
        NatsJetstreamPublish,
        jetstream=jetstream,
    )
