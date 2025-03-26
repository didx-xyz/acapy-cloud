from logging import Logger
from typing import Any, Dict, Literal, Optional

import orjson
from pydantic import BaseModel


class Endorsement(BaseModel):
    state: Literal[
        "request-received",
        "request-sent",
        "transaction-acked",
        "transaction-cancelled",
        "transaction-created",
        "transaction-endorsed",
        "transaction-refused",
        "transaction-resent",
        "transaction-resent_received",
    ]
    transaction_id: str


def extract_operation_type_from_endorsement_payload(
    payload: Dict[str, Any], logger: Logger
) -> Optional[str]:
    """Safely extracts the 'type' value from a nested endorsement payload.

    Args:
        payload (Dict[str, Any]): The endorsement event payload.
        logger (Logger): A logging object, of course.

    Returns:
        Optional[str]: The extracted type value, or None if not found.
    """
    # Attempt to navigate through the nested structure
    messages_attach = payload.get("messages_attach", [])
    if not messages_attach:
        logger.debug("No `messages_attach` found in endorsement payload.")
        return None  # Early return if 'messages_attach' is empty or does not exist

    try:
        for message in messages_attach:
            data = message.get("data")
            if data:
                json_payload = data.get("json")
                if json_payload:
                    if isinstance(json_payload, str):
                        json_dict = orjson.loads(json_payload)
                    elif isinstance(json_payload, dict):
                        json_dict = json_payload
                    else:
                        logger.warning("Unexpected json payload: {}", json_payload)
                        return None

                    operation = json_dict.get("operation")
                    if operation:
                        operation_type = operation.get("type")
                        if operation_type:
                            return operation_type  # Successfully found the type
    except orjson.JSONDecodeError as e:
        logger.warning(
            "Couldn't extract json payload from {}. {}. Continuing...", json_payload, e
        )
    except Exception as e:  # pylint: disable=W0718
        logger.warning(
            "Exception while extracting operation type from endorsement payload. {}. Continuing...",
            e,
        )

    return None  # Return None if the type could not be found or if error occurred


class TransactionTypes:
    # See acapy-agent-python/aries_cloudagent/ledger/merkel_validation/constants.py
    ATTRIB = "100"
    SCHEMA = "101"
    CLAIM_DEF = "102"
    REVOC_REG_DEF = "113"
    REVOC_REG_ENTRY = "114"


applicable_transaction_state = "request_received"

valid_operation_types = [
    TransactionTypes.ATTRIB,
    TransactionTypes.SCHEMA,
    TransactionTypes.CLAIM_DEF,
    TransactionTypes.REVOC_REG_DEF,
    TransactionTypes.REVOC_REG_ENTRY,
]


def payload_is_applicable_for_endorser(payload: Dict[str, Any], logger: Logger) -> bool:
    transaction_id = payload.get("transaction_id")
    if not transaction_id:
        logger.warning("No transaction id associated with this endorsement event")
        return False

    state = payload.get("state")

    if state == applicable_transaction_state:
        logger.debug("Endorsement payload in eligible state: {}", state)
    else:
        logger.debug("Endorsement payload not in eligible state: {}", state)
        return False

    operation_type = extract_operation_type_from_endorsement_payload(payload, logger)

    if not operation_type:
        logger.debug("Could not extract an operation type from payload.")
        return False

    is_applicable = operation_type in valid_operation_types
    if is_applicable:
        logger.info(
            "Payload is applicable for endorsement, with operation type: {}.",
            operation_type,
        )
    else:
        logger.warning(  # Because we should only receive applicable operation types
            "Payload is NOT applicable for endorsement, with operation type {}.",
            operation_type,
        )
    return is_applicable


def obfuscate_primary_data_in_payload(
    payload: Dict[str, Any], logger: Logger
) -> Dict[str, Any]:
    # Endorsement event payloads can contain a key called "master_secret", which we will obfuscate.
    # This value is deeply nested in the payload, as part of the `json` string
    # within `messages_attach: [{`data`:{...}}]`, or in `signature_response: [{signature: {"<did>: {...}}]`

    mask = "[REDACTED]"  # string to replace with

    payload_copy = payload.copy()

    # Iterate over each 'messages_attach' item, if it exists
    for message_attach in payload_copy.get("messages_attach", []):
        # Ensure 'data' and 'data['json']' fields exist and contain JSON strings
        if "data" in message_attach and "json" in message_attach["data"]:
            try:
                # Parse the JSON string in 'data['json']'
                data_json = orjson.loads(message_attach["data"]["json"])

                # Check if the 'primary' field exists in the parsed JSON and obfuscate it
                if "operation" in data_json and "data" in data_json["operation"]:
                    if "primary" in data_json["operation"]["data"]:
                        data_json["operation"]["data"]["primary"] = mask

                    # While we are here, let's obfuscate the revocation field too. Big payload with many irrelevant keys
                    if "revocation" in data_json["operation"]["data"]:
                        data_json["operation"]["data"]["revocation"] = mask

                # Replace the original JSON string with the modified version
                message_attach["data"]["json"] = orjson.dumps(data_json).decode()

            except orjson.JSONDecodeError:
                logger.debug("Could not parse json in message_attach")

    # Iterate over each 'signature_response' item, if it exists
    for signature_response in payload_copy.get("signature_response", []):
        # Ensure 'data' and 'data['json']' fields exist and contain JSON strings
        if "signature" in signature_response:
            for did, signature_json_str in signature_response["signature"].items():
                try:
                    signature_json = orjson.loads(signature_json_str)
                    if (
                        "operation" in signature_json
                        and "data" in signature_json["operation"]
                        and "primary" in signature_json["operation"]["data"]
                    ):
                        signature_json["operation"]["data"]["primary"] = mask

                    # Replace the original JSON string with the modified version
                    signature_response["signature"][did] = orjson.dumps(
                        signature_json
                    ).decode()

                except orjson.JSONDecodeError:
                    logger.debug("Could not parse json in signature_response")

    return payload_copy
