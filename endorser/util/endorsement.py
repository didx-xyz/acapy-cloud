import asyncio
from typing import Any, Dict, Optional

from aries_cloudcontroller import AcaPyClient, TransactionRecord
from fastapi import HTTPException

from endorser.util.transaction_record import (
    get_did_and_schema_id_from_cred_def_attachment,
    get_endorsement_request_attachment,
    is_attrib_type,
    is_credential_definition_transaction,
    is_revocation_def_or_entry,
    is_schema_type,
)
from endorser.util.trust_registry import is_valid_issuer
from shared.log_config import get_logger
from shared.models.endorsement import applicable_transaction_state

logger = get_logger(__name__)


async def should_accept_endorsement(
    client: AcaPyClient, transaction_id: str
) -> Optional[TransactionRecord]:
    """Check whether a transaction endorsement request should be endorsed.

    Whether the request should be accepted is based on the follow criteria:
    1. The transaction is for a credential definition
    2. The did is registered as an issuer in the trust registry.
    3. The schema_id is registered in the trust registry.

    Args:
        transaction_id (str): The transaction id for this endorsement request

    Returns:
        Optional[TransactionRecord]: The transaction record if it should be endorsed, None otherwise
    """
    bound_logger = logger.bind(body={"transaction_id": transaction_id})
    bound_logger.debug("Validating if endorsement transaction should be endorsed")

    bound_logger.debug("Fetching transaction with id: `{}`", transaction_id)
    transaction = await client.endorse_transaction.get_transaction(
        tran_id=transaction_id
    )

    if transaction.state != applicable_transaction_state:
        bound_logger.warning(
            "Endorsement event for transaction with id `{}` "
            "not in state '{}' (is `{}`).",
            transaction_id,
            applicable_transaction_state,
            transaction.state,
        )
        return None

    attachment = get_endorsement_request_attachment(transaction)
    if not attachment:
        bound_logger.warning("Could not extract attachment from transaction.")
        return None

    operation_type = await extract_operation_type(attachment)
    if not operation_type:
        # The request to register a DID on ledger has no operation type, but has signature request
        if await is_signature_request_applicable(transaction):
            return transaction
        return None

    if await check_applicable_operation_type(
        client, transaction_id, operation_type, attachment
    ):
        return transaction
    return None


async def extract_operation_type(attachment: Dict[str, Any]) -> Optional[str]:
    operation = attachment.get("operation")
    if not operation:
        logger.debug("Key `operation` not in attachment: `{}`.", attachment)
        return None

    operation_type = operation.get("type")
    if not operation_type:
        logger.debug("Key `type` not in operation attachment.")
        return None

    return operation_type


async def is_signature_request_applicable(transaction: TransactionRecord) -> bool:
    """
    Check if the signature_request in the transaction has the required author_goal_code.

    Args:
        transaction: The transaction object to check.

    Returns:
        bool: True if the signature_request is applicable, False otherwise.
    """
    signature_request = transaction.signature_request
    if not signature_request or not isinstance(signature_request, list):
        logger.debug("No valid signature_request found in transaction.")
        return False

    first_request = signature_request[0]
    author_goal_code = first_request.get("author_goal_code")
    if author_goal_code == "aries.transaction.register_public_did":
        logger.debug("Transaction is applicable based on signature_request.")
        return True

    logger.debug("Transaction is not applicable based on signature_request.")
    return False


async def check_applicable_operation_type(
    client: AcaPyClient,
    transaction_id: str,
    operation_type: str,
    attachment: Dict[str, Any],
) -> bool:
    bound_logger = logger.bind(body={"transaction_id": transaction_id})

    if is_schema_type(operation_type):
        bound_logger.debug("Endorsement request is for SCHEMA type.")
        return True

    if is_revocation_def_or_entry(operation_type):
        bound_logger.debug("Endorsement request is for revocation definition or entry.")
        return True

    if is_attrib_type(operation_type):
        bound_logger.debug("Endorsement request is for ATTRIB type.")
        return True

    if not is_credential_definition_transaction(operation_type, attachment):
        bound_logger.warning("Endorsement request is not for credential definition.")
        return False

    # Here, endorsement request is for credential definition
    did, schema_id = await get_did_and_schema_id_from_cred_def_attachment(
        client, attachment
    )

    return await retry_is_valid_issuer(did, schema_id, transaction_id)


async def retry_is_valid_issuer(
    did: str,
    schema_id: str,
    transaction_id: str,
    max_retries: int = 5,
    retry_delay: float = 1.0,
) -> bool:
    bound_logger = logger.bind(body={"transaction_id": transaction_id})
    for attempt in range(max_retries):
        try:
            valid_issuer = await is_valid_issuer(did, schema_id)

            if not valid_issuer:
                bound_logger.warning(
                    "Endorsement request with transaction id `{}` is not for did "
                    "and schema registered in the trust registry.",
                    transaction_id,
                )
                return False

            return True

        except HTTPException as e:
            bound_logger.error(
                "Attempt {}: Exception caught when asserting valid issuer: {}",
                attempt + 1,
                e,
            )

            if attempt < max_retries - 1:
                bound_logger.warning("Retrying in {}s ...", retry_delay)
                await asyncio.sleep(retry_delay)
            else:
                bound_logger.error("Max retries reached. Giving up.")
                return False


async def accept_endorsement(client: AcaPyClient, transaction_id: str) -> None:
    logger.info("Endorsing transaction with id: `{}`", transaction_id)
    await client.endorse_transaction.endorse_transaction(tran_id=transaction_id)
