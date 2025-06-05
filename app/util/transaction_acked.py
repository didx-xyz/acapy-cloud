import asyncio

from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.util.retry_method import coroutine_with_retry_until_value
from shared.log_config import get_logger

logger = get_logger(__name__)


async def wait_for_transaction_ack(
    aries_controller: AcaPyClient,
    transaction_id: str,
    max_attempts: int = 15,
    retry_delay: int = 1,
) -> None:
    """Wait for the transaction to be acknowledged by the endorser."""
    bound_logger = logger.bind(transaction_id=transaction_id)
    bound_logger.debug("Waiting for transaction to be acknowledged by the endorser")
    try:
        # Wait for transaction to be acknowledged and written to the ledger
        await coroutine_with_retry_until_value(
            coroutine_func=aries_controller.endorse_transaction.get_transaction,
            args=(transaction_id,),
            field_name="state",
            expected_value="transaction_acked",
            logger=bound_logger,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
        )
    except asyncio.TimeoutError as e:
        raise CloudApiException(
            "Timeout waiting for endorser to accept the endorsement request.",
            504,
        ) from e
    bound_logger.debug("Transaction has been acknowledged by the endorser")
