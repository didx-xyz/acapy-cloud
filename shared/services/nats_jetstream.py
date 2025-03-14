from datetime import datetime, timedelta
from typing import Any, AsyncGenerator

import nats
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrNoServers, ErrTimeout
from nats.js.client import JetStreamContext

from shared.constants import NATS_CREDS_FILE, NATS_SERVER
from shared.log_config import get_logger

logger = get_logger(__name__)

# State tracking for connection issues
last_disconnect_time = None
reconnect_attempts = 0
RECONNECT_THRESHOLD = 5  # Seconds for quick reconnect (restart)
MAX_ATTEMPTS_BEFORE_ERROR = 2  # Attempts before escalating to error


async def init_nats_client() -> AsyncGenerator[JetStreamContext, Any]:
    """
    Initialize a connection to the NATS server with robust error differentiation.
    """
    logger.debug("Initialise NATS server ...")

    connect_kwargs = {
        "servers": [NATS_SERVER],
        "reconnect_time_wait": 1,  # 1-second wait between attempts
        "max_reconnect_attempts": -1,  # Infinite attempts (we'll handle escalation)
        "error_cb": error_callback,
        "disconnected_cb": disconnected_callback,
        "reconnected_cb": reconnected_callback,
        "closed_cb": closed_callback,
    }

    if NATS_CREDS_FILE:
        connect_kwargs["user_credentials"] = NATS_CREDS_FILE
    else:
        logger.warning("No NATS credentials file found, assuming local development")

    logger.info("Connecting to NATS server with kwargs {} ...", connect_kwargs)

    try:
        nats_client: NATS = await nats.connect(**connect_kwargs)
    except (ErrConnectionClosed, ErrTimeout, ErrNoServers) as e:
        logger.error("Failed to establish initial NATS connection: {}", e)
        raise e  # Initial failure is always an error

    logger.debug("Connected to NATS server")
    jetstream: JetStreamContext = nats_client.jetstream()
    logger.debug("Yielding JetStream context ...")

    try:
        yield jetstream
    finally:
        logger.debug("Closing NATS connection ...")
        await nats_client.close()
        logger.debug("NATS connection closed")


async def error_callback(e):
    # Log specific critical errors as errors
    if isinstance(e, (ErrNoServers, ErrTimeout, ErrConnectionClosed)):
        logger.error("Critical NATS connection issue: {}", str(e))
    elif "authentication" in str(e).lower() or "authorization" in str(e).lower():
        logger.error("NATS authentication/authorization failure: {}", str(e))
    else:
        logger.warning("NATS operational issue (possibly transient): {}", str(e))


async def disconnected_callback():
    global last_disconnect_time, reconnect_attempts
    last_disconnect_time = datetime.utcnow()
    reconnect_attempts += 1
    if reconnect_attempts == 1:
        logger.warning("Disconnected from NATS server; attempting reconnect")
    elif reconnect_attempts >= MAX_ATTEMPTS_BEFORE_ERROR:
        logger.error(
            "Persistent NATS disconnection after {} attempts; potential issue",
            reconnect_attempts,
        )


async def reconnected_callback():
    global last_disconnect_time, reconnect_attempts
    if last_disconnect_time:
        time_since_disconnect = (
            datetime.utcnow() - last_disconnect_time
        ).total_seconds()
        if (
            time_since_disconnect < RECONNECT_THRESHOLD
            and reconnect_attempts < MAX_ATTEMPTS_BEFORE_ERROR
        ):
            logger.info(
                "Reconnected to NATS server after brief disconnect (likely restart): {}s",
                time_since_disconnect,
            )
        else:
            logger.warning(
                "Reconnected to NATS server after delay or multiple attempts: {}s, attempts={}",
                time_since_disconnect,
                reconnect_attempts,
            )
    else:
        logger.info("Reconnected to NATS server")
    # Reset state on successful reconnect
    last_disconnect_time = None
    reconnect_attempts = 0


async def closed_callback():
    logger.info("NATS connection closed intentionally")
