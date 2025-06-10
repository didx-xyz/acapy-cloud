import asyncio
import os
from collections.abc import Callable
from logging import Logger

from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException, handle_acapy_call

DEFAULT_NUM_TRIES = 1
DEFAULT_DELAY = float(os.environ.get("SET_ENDORSER_INFO_DELAY", "1.5"))


# todo: Migrate to endorser service
async def set_endorser_role(
    *,
    endorser_controller: AcaPyClient,
    endorser_connection_id: str,
    logger: Logger,
    delay: float = DEFAULT_DELAY,
):
    try:
        logger.debug("Setting roles for endorser on endorser-issuer connection.")
        await handle_acapy_call(
            logger=logger,
            acapy_call=endorser_controller.endorse_transaction.set_endorser_role,
            conn_id=endorser_connection_id,
            transaction_my_job="TRANSACTION_ENDORSER",
        )
        logger.debug("Successfully set endorser role.")
        await asyncio.sleep(delay)  # Allow ACA-Py records to update
    except CloudApiException as e:
        logger.error("Failed to set endorser role: {}.", e)
        raise CloudApiException(
            "Failed to set the endorser role in the endorser-issuer connection, "
            f"with connection id {endorser_connection_id}. "
            "This is a known bug in ACA-Py. Please retry."
        ) from e


async def set_author_role(
    *,
    issuer_controller: AcaPyClient,
    issuer_connection_id: str,
    logger: Logger,
    delay: float = DEFAULT_DELAY,
):
    try:
        logger.debug("Setting roles for author on issuer-endorser connection")
        await handle_acapy_call(
            logger=logger,
            acapy_call=issuer_controller.endorse_transaction.set_endorser_role,
            conn_id=issuer_connection_id,
            transaction_my_job="TRANSACTION_AUTHOR",
        )
        logger.debug("Successfully set author role.")
        await asyncio.sleep(delay)  # Allow ACA-Py records to update
    except CloudApiException as e:
        logger.error("Failed to set author role: {}.", e)
        raise CloudApiException(
            "Failed to set the author role in the issuer-endorser connection, "
            f"with connection id {issuer_connection_id}. "
            "This is a known bug in ACA-Py. Please retry."
        ) from e


async def set_endorser_info(
    *,
    issuer_controller: AcaPyClient,
    issuer_connection_id: str,
    endorser_did: str,
    logger: Logger,
    delay: float = DEFAULT_DELAY,
):
    try:
        logger.debug("Setting endorser info on issuer-endorser connection")
        await handle_acapy_call(
            logger=logger,
            acapy_call=issuer_controller.endorse_transaction.set_endorser_info,
            conn_id=issuer_connection_id,
            endorser_did=endorser_did,
        )
        logger.debug("Successfully set endorser info.")
        await asyncio.sleep(delay)  # Allow ACA-Py records to update
    except CloudApiException as e:
        logger.error("Failed to set endorser info: {}.", e)
        raise CloudApiException(
            "Failed to set the endorser info in the issuer-endorser connection, "
            f"with connection id {issuer_connection_id}. "
            "This is a known bug in ACA-Py. Please retry."
        ) from e


# Unused code at the moment: may be useful in avoiding ACA-Py delays resulting in duplicate record bug


async def assert_metadata_set(
    controller: AcaPyClient,
    conn_id: str,
    check_fn: Callable,
    logger: Logger,
    num_tries=DEFAULT_NUM_TRIES,
    delay=DEFAULT_DELAY,
):
    """Checks if connection record metadata has been set according to a custom check function.

    Args:
        controller: The AcaPyClient instance for the respective agent
        conn_id: Connection id of the connection you're interested in
        check_fn: A function that takes the metadata and returns True if it meets the desired condition
        logger: A logger instance
        num_tries: Number of num_tries before failing
        delay: Delay in seconds between each retry

    Returns:
        True if condition is met, raises an exception otherwise.

    """
    for _ in range(num_tries):
        # Delay is placed at the start to avoid race condition in ACA-Py, where reading metadata causes duplicate
        # record error if metadata is still due to be updated
        logger.debug("Sleep {}s before trying to fetch metadata", delay)
        await asyncio.sleep(delay)
        try:
            logger.debug("Fetching connection metadata")
            connection_metadata = await handle_acapy_call(
                logger=logger,
                acapy_call=controller.connection.get_metadata,
                conn_id=conn_id,
            )
            logger.debug("Successfully fetched metadata")
            metadata_dict = connection_metadata.results
            if check_fn(metadata_dict):
                return True
        except CloudApiException as e:
            logger.error("Exception occurred when getting metadata: {}", e)

    raise SettingMetadataException(
        f"Failed to assert that metadata meets the desired condition after {num_tries} attempts."
    )


async def assert_endorser_role_set(
    controller: AcaPyClient,
    conn_id: str,
    logger: Logger,
    num_tries=1,
    delay=DEFAULT_DELAY,
):
    def check_fn(metadata: dict):
        return (
            metadata.get("transaction_jobs", {}).get("transaction_my_job")
            == "TRANSACTION_ENDORSER"
        )

    try:
        await assert_metadata_set(
            controller, conn_id, check_fn, logger, num_tries, delay
        )
    except Exception as e:
        raise SettingMetadataException(
            "Failed to assert that the endorser role has been set in the connection metadata."
        ) from e


async def assert_author_role_set(
    controller: AcaPyClient,
    conn_id: str,
    logger: Logger,
    num_tries=1,
    delay=DEFAULT_DELAY,
):
    def check_fn(metadata: dict):
        return (
            metadata.get("transaction_jobs", {}).get("transaction_my_job")
            == "TRANSACTION_AUTHOR"
            and metadata.get("transaction_jobs", {}).get("transaction_their_job")
            == "TRANSACTION_ENDORSER"
        )

    try:
        await assert_metadata_set(
            controller, conn_id, check_fn, logger, num_tries, delay
        )
    except Exception as e:
        raise SettingMetadataException(
            "Failed to assert that the author role has been set in the connection metadata."
        ) from e


async def assert_endorser_info_set(
    controller: AcaPyClient,
    conn_id: str,
    endorser_did: str,
    logger: Logger,
    num_tries=1,
    delay=DEFAULT_DELAY,
):
    def check_fn(metadata: dict):
        return (
            metadata.get("transaction_jobs", {}).get("transaction_my_job")
            == "TRANSACTION_AUTHOR"
            and metadata.get("transaction_jobs", {}).get("transaction_their_job")
            == "TRANSACTION_ENDORSER"
            and metadata.get("endorser_info", {}).get("endorser_did") == endorser_did
        )

    try:
        await assert_metadata_set(
            controller, conn_id, check_fn, logger, num_tries, delay
        )
    except Exception as e:
        raise SettingMetadataException(
            "Failed to assert that the endorser info has been set in the connection metadata."
        ) from e


class SettingMetadataException(CloudApiException):
    pass
