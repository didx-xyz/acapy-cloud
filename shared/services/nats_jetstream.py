from typing import Any, AsyncGenerator

import nats
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrNoServers, ErrTimeout
from nats.js.client import JetStreamContext

from shared.constants import NATS_CREDS_FILE, NATS_SERVER
from shared.log_config import get_logger

logger = get_logger(__name__)


async def init_nats_client() -> AsyncGenerator[JetStreamContext, Any]:
    """
    Initialize a connection to the NATS server.
    """
    logger.debug("Initialise NATS server ...")

    connect_kwargs = {"servers": [NATS_SERVER]}
    if NATS_CREDS_FILE:
        connect_kwargs["user_credentials"] = NATS_CREDS_FILE
    else:
        logger.warning("No NATS credentials file found, assuming local development")

    logger.info("Connecting to NATS server with kwargs {} ...", connect_kwargs)
    try:
        nats_client: NATS = await nats.connect(**connect_kwargs)

    except (ErrConnectionClosed, ErrTimeout, ErrNoServers) as e:
        logger.error("Error connecting to NATS server: {}", e)
        raise e
    logger.debug("Connected to NATS server")

    jetstream: JetStreamContext = nats_client.jetstream()
    logger.debug("Yielding JetStream context ...")
    yield jetstream

    logger.debug("Closing NATS connection ...")
    await nats_client.close()
    logger.debug("NATS connection closed")
