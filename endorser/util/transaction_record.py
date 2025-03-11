from typing import Any, Dict, Optional, Tuple

import orjson
from aries_cloudcontroller import AcaPyClient, TransactionRecord

from endorser.services.endorser_config import EndorserConfig
from shared.log_config import get_logger
from shared.models.endorsement import TransactionTypes

logger = get_logger(__name__)


def get_endorsement_request_attachment(
    transaction: TransactionRecord,
) -> Optional[Dict[str, Any]]:
    try:
        if not transaction.messages_attach:
            logger.warning("No message attachments in transaction")
            return None

        attachment: Dict = transaction.messages_attach[0]
        json_payload = attachment["data"]["json"]

        # Both dict and str encoding have occurred for the attachment data
        # Parse to dict if payload is of type str
        if isinstance(json_payload, str):
            logger.debug("Try cast attachment payload to json")
            json_payload = orjson.loads(json_payload)
            logger.debug("Payload is valid JSON.")

        return json_payload

    except (IndexError, KeyError, TypeError):
        logger.warning("Could not read attachment from transaction: `{}`.", transaction)
    except orjson.JSONDecodeError:
        logger.warning("Failed to decode attachment payload. Invalid JSON.")

    return None


def is_credential_definition_transaction(
    operation_type: str, attachment: Dict[str, Any]
) -> bool:
    # credential definition type is 102
    # see https://github.com/hyperledger/indy-node/blob/master/docs/source/requests.md#common-request-structure
    if operation_type != TransactionTypes.CLAIM_DEF:
        return False

    if "identifier" not in attachment:
        logger.warning(
            "Expected key `identifier` does not exist in extracted attachment. Got attachment: `{}`.",
            attachment,
        )
        return False

    # `operation` key is already asserted to exist in `extract_operation_type`
    if "ref" not in attachment["operation"]:
        logger.warning(
            "Expected key `ref` does not exist in attachment `operation`. Got operation: `{}`.",
            attachment["operation"],
        )
        return False

    return True


async def get_did_and_schema_id_from_cred_def_attachment(
    client: AcaPyClient, attachment: Dict[str, Any]
) -> Tuple[str, str]:
    did = "did:sov:" + attachment["identifier"]
    schema_seq_id = attachment["operation"]["ref"]

    wallet_type = EndorserConfig().wallet_type  # Get wallet type from config singleton
    if wallet_type == "askar-anoncreds":
        logger.debug("Fetching anoncreds schema with id: `{}`", schema_seq_id)
        schema = await client.anoncreds_schemas.get_schema(schema_id=str(schema_seq_id))
        schema_id = schema.schema_id
    else:  # askar
        logger.debug("Fetching indy schema with id: `{}`", schema_seq_id)
        schema = await client.schema.get_schema(schema_id=str(schema_seq_id))
        schema_id = schema.var_schema.id if schema.var_schema else None

    if not schema_id:
        raise ValueError(f"Could not extract schema id from schema response: {schema}.")
    return (did, schema_id)


def is_attrib_type(operation_type: str) -> bool:
    return operation_type == TransactionTypes.ATTRIB


def is_revocation_def_or_entry(operation_type: str) -> bool:
    return operation_type in [
        TransactionTypes.REVOC_REG_DEF,
        TransactionTypes.REVOC_REG_ENTRY,
    ]
