import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.errors import (
    AuthorizationError,
    ConnectionClosedError,
    NoServersError,
    UnexpectedEOF,
)
from nats.js.client import JetStreamContext

from shared.constants import NATS_CREDS_FILE, NATS_SERVER
from shared.log_config import get_logger

logger = get_logger(__name__)

# State tracking for connection issues
RECONNECT_THRESHOLD = int(
    os.getenv("NATS_RECONNECT_THRESHOLD", "5")  # Seconds for quick reconnect (restart)
)
MAX_ATTEMPTS_BEFORE_ERROR = int(
    os.getenv(
        "NATS_MAX_ATTEMPTS_BEFORE_ERROR",
        "2",  # Attempts before escalating to error
    )
)


class NATSStatus:
    def __init__(self) -> None:
        """Initialize the NATS status tracker."""
        self.last_disconnect_time = None
        self.reconnect_attempts = 0

    def _reset(self) -> None:
        self.__init__()

    async def error_callback(self, e: Exception) -> None:
        error_str = str(e).lower()
        if isinstance(e, UnexpectedEOF):
            logger.warning("NATS unexpected EOF error: {}", e)
        elif isinstance(e, NoServersError | TimeoutError | ConnectionClosedError):
            logger.error("Critical NATS connection issue: {}", e)
        elif isinstance(e, AuthorizationError):
            logger.error("NATS authentication/authorization failure: {}", e)
        elif "empty response from server" in error_str:
            logger.error("NATS server unavailable during connection attempt: {}", e)
        elif self.last_disconnect_time is None:
            logger.error("NATS operational error: {}", e)
        else:
            seconds_since_disconnect = time.time() - self.last_disconnect_time
            if seconds_since_disconnect < RECONNECT_THRESHOLD:
                logger.warning("NATS operational error during reconnection: {}", e)
            else:
                logger.error(
                    "NATS operational error. Exceeded reconnect ({}s): {}",
                    seconds_since_disconnect,
                    e,
                )

    async def disconnected_callback(self) -> None:
        self.last_disconnect_time = time.time()
        self.reconnect_attempts += 1
        if self.reconnect_attempts >= MAX_ATTEMPTS_BEFORE_ERROR:
            logger.error(
                "Persistent NATS disconnection after {} attempts; cluster may be unavailable",
                self.reconnect_attempts,
            )
        else:
            logger.warning(
                "Disconnected from NATS server; attempting reconnect (possibly due to scale-down)"
            )

    async def reconnected_callback(self) -> None:
        if self.last_disconnect_time:
            seconds_since_disconnect = time.time() - self.last_disconnect_time
            if (
                seconds_since_disconnect < RECONNECT_THRESHOLD
                and self.reconnect_attempts < MAX_ATTEMPTS_BEFORE_ERROR
            ):
                logger.info(
                    "Reconnected to NATS server after: {}s",
                    seconds_since_disconnect,
                )
            else:
                logger.warning(
                    "Reconnected to NATS server after delay or multiple attempts: {}s, attempts={}",
                    seconds_since_disconnect,
                    self.reconnect_attempts,
                )
        else:
            logger.info("Reconnected to NATS server")
        # Reset state on successful reconnect
        self._reset()

    async def closed_callback(self) -> None:
        logger.info("NATS connection closed")


async def init_nats_client() -> AsyncGenerator[JetStreamContext, Any]:
    """Initialize a connection to the NATS server with robust error differentiation."""
    logger.debug("Initialise NATS server ...")

    nats_status = NATSStatus()

    connect_kwargs = {
        "servers": [NATS_SERVER],
        "reconnect_time_wait": 1,  # 1-second wait between attempts
        "max_reconnect_attempts": -1,  # Infinite attempts (we'll handle escalation)
        "error_cb": nats_status.error_callback,
        "disconnected_cb": nats_status.disconnected_callback,
        "reconnected_cb": nats_status.reconnected_callback,
        "closed_cb": nats_status.closed_callback,
    }

    if NATS_CREDS_FILE:
        connect_kwargs["user_credentials"] = NATS_CREDS_FILE
    else:
        logger.warning("No NATS credentials file found, assuming local development")

    logger.info("Connecting to NATS server with kwargs {} ...", connect_kwargs)

    try:
        nats_client: NATSClient = await nats.connect(**connect_kwargs)
    except (NoServersError, TimeoutError, ConnectionClosedError) as e:
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
