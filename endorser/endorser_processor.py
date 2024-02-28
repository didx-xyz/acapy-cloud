import asyncio
import json
from typing import Any, Dict, Optional

from aries_cloudcontroller import AcaPyClient, TransactionRecord
from fastapi import HTTPException
from fastapi_websocket_pubsub import PubSubClient
from pydantic import BaseModel

from shared import (
    GOVERNANCE_AGENT_API_KEY,
    GOVERNANCE_AGENT_URL,
    TRUST_REGISTRY_URL,
    WEBHOOKS_PUBSUB_URL,
)
from shared.log_config import get_logger
from shared.models.webhook_topics import Endorsement
from shared.util.rich_async_client import RichAsyncClient
from shared.util.rich_parsing import parse_with_error_handling

logger = get_logger(__name__)


class Event(BaseModel):
    payload: Dict[str, Any]
    origin: str
    wallet_id: str


async def listen_endorsement_events():
    topic = "endorsements-governance"

    client = PubSubClient([topic], callback=process_endorsement_event)
    logger.debug("Opening connection to webhook server")
    client.start_client(WEBHOOKS_PUBSUB_URL)
    logger.debug("Opened connection to webhook server. Waiting for readiness...")
    await client.wait_until_ready()
    logger.debug("Connection to webhook server ready")
    logger.info(
        "Listening for 'endorsements' events from webhook server at {}.",
        WEBHOOKS_PUBSUB_URL,
    )


# topic is unused, but passed by the fastapi library.
async def process_endorsement_event(data: str, topic: str):
    event: Event = parse_with_error_handling(Event, data)
    logger.debug(
        "Processing endorsement event for agent `{}` and wallet `{}`",
        event.origin,
        event.wallet_id,
    )
    # We're only interested in events from the governance agent
    if not is_governance_agent(event):
        logger.debug("Endorsement request is not for governance agent.")
        return

    endorsement = Endorsement(**event.payload)

    async with AcaPyClient(
        base_url=GOVERNANCE_AGENT_URL, api_key=GOVERNANCE_AGENT_API_KEY
    ) as client:
        # Not interested in this endorsement request
        if not await should_accept_endorsement(client, endorsement):
            logger.debug(
                "Endorsement request with transaction id `{}` is not applicable for endorsement.",
                endorsement.transaction_id,
            )
            return

        logger.info(
            "Endorsement request with transaction id `{}` is applicable for endorsement, accepting request.",
            endorsement.transaction_id,
        )
        await accept_endorsement(client, endorsement)


def is_governance_agent(event: Event):
    return event.origin == "governance"


async def should_accept_endorsement(
    client: AcaPyClient, endorsement: Endorsement
) -> bool:
    """Check whether a transaction endorsement request should be endorsed.

    Whether the request should be accepted is based on the follow criteria:
    1. The transaction is for a credential definition
    2. The did is registered as an issuer in the trust registry.
    3. The schema_id is registered in the trust registry.

    Args:
        endorsement (Endorsement): The endorsement event model

    Returns:
        bool: Whether the endorsement request should be accepted
    """
    bound_logger = logger.bind(body=endorsement)
    bound_logger.debug("Validating if endorsement transaction should be endorsed")

    transaction_id = endorsement.transaction_id
    bound_logger.debug("Fetching transaction with id: `{}`", transaction_id)
    transaction = await client.endorse_transaction.get_transaction(
        tran_id=transaction_id
    )

    if transaction.state != "request_received":
        bound_logger.debug(
            "Endorsement event for transaction with id `{}` "
            "not in state 'request_received' (is `{}`).",
            transaction_id,
            transaction.state,
        )
        return False

    attachment = get_endorsement_request_attachment(transaction)

    if not attachment:
        bound_logger.debug("Could not extract attachment from transaction.")
        return False

    if not is_credential_definition_transaction(attachment):
        bound_logger.debug("Endorsement request is not for credential definition.")
        return False

    if "identifier" not in attachment:
        bound_logger.debug(
            "Expected key `identifier` does not exist in extracted attachment. Got attachment: `{}`.",
            attachment,
        )
        return False

    # `operation` key is asserted to exist in `is_credential_definition_transaction`
    if "ref" not in attachment["operation"]:
        bound_logger.debug(
            "Expected key `ref` does not exist in attachment `operation`. Got operation: `{}`.",
            attachment["operation"],
        )
        return False

    did, schema_id = await get_did_and_schema_id_from_cred_def_attachment(
        client, attachment
    )

    max_retries = 5
    retry_delay = 1  # in seconds

    for attempt in range(max_retries):
        try:
            valid_issuer = await is_valid_issuer(did, schema_id)

            if not valid_issuer:
                bound_logger.info(
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
                bound_logger.info("Retrying...")
                await asyncio.sleep(retry_delay)
            else:
                bound_logger.error("Max retries reached. Giving up.")
                return False


async def get_did_and_schema_id_from_cred_def_attachment(
    client: AcaPyClient, attachment: Dict[str, Any]
):
    did = "did:sov:" + attachment["identifier"]
    schema_seq_id = attachment["operation"]["ref"]

    logger.debug("Fetching schema with seq id: `{}`", schema_seq_id)
    schema = await client.schema.get_schema(schema_id=str(schema_seq_id))

    if not schema.var_schema or not schema.var_schema.id:
        raise Exception("Could not extract schema id from schema response.")

    schema_id = schema.var_schema.id

    return (did, schema_id)


def get_endorsement_request_attachment(
    transaction: TransactionRecord,
) -> Optional[Dict[str, Any]]:
    try:
        if not transaction.messages_attach:
            logger.debug("No message attachments in transaction")
            return None

        attachment: Dict = transaction.messages_attach[0]

        if "data" not in attachment:
            logger.debug(
                "Attachment does not contain expected key `data`. Got attachment: `{}`.",
                attachment,
            )
            return None

        if not isinstance(attachment["data"], dict) or "json" not in attachment["data"]:
            logger.debug(
                "Attachment data does not contain expected keys `json`. Got attachment data: `{}`.",
                attachment["data"],
            )
            return None

        json_payload = attachment["data"]["json"]

        # Both dict and str encoding have ocurred for the attachment data
        # Parse to dict if payload is of type str
        if isinstance(json_payload, str):
            logger.debug("Try cast attachment payload to json")
            try:
                json_payload = json.loads(json_payload)
                logger.debug("Payload is valid JSON.")
            except json.JSONDecodeError:
                logger.warning("Failed to decode attachment payload. Invalid JSON.")
                json_payload = None

        return json_payload
    except (TypeError, KeyError):
        logger.warning(f"Could not read attachment from transaction: `{transaction}`.")
    except Exception:
        logger.exception(
            "Exception caught while running `get_endorsement_request_attachment`."
        )
    return None


def is_credential_definition_transaction(attachment: Dict[str, Any]) -> bool:
    try:
        if "operation" not in attachment:
            logger.debug("Key `operation` not in attachment: `{}`.", attachment)
            return False

        operation = attachment["operation"]

        if "type" not in operation:
            logger.debug("Key `type` not in operation attachment.")
            return False

        logger.debug(
            "Endorsement request operation type: `{}`. Must be 102 for credential definition",
            operation.get("type"),
        )
        # credential definition type is 102
        # see https://github.com/hyperledger/indy-node/blob/master/docs/source/requests.md#common-request-structure

        return operation.get("type") == "102"
    except Exception:
        logger.exception(
            "Exception caught while running `is_credential_definition_transaction`."
        )
        return False


async def is_valid_issuer(did: str, schema_id: str):
    """Assert that an actor with the specified did is registered as issuer.

    This method asserts that there is an actor registered in the trust registry
    with the specified did. It verifies whether this actor has the `issuer` role
    and will also make sure the specified schema_id is registered as a valid schema.
    Raises an exception if one of the assertions fail.

    NOTE: the dids in the registry are registered as fully qualified dids. This means
    when passing a did to this method it must also be fully qualified (e.g. `did:sov:xxxx`)

    Args:
        did (str): the did of the issuer in fully qualified format.
        schema_id (str): the schema_id of the credential being issued

    Raises:
        Exception: When the did is not registered, the actor doesn't have the issuer role
            or the schema is not registered in the registry.
    """
    bound_logger = logger.bind(body={"did": did, "schema_id": schema_id})
    bound_logger.debug("Assert that did is registered as issuer")
    try:
        async with RichAsyncClient() as client:
            bound_logger.debug("Fetch actor with did `{}` from trust registry", did)
            actor_res = await client.get(
                f"{TRUST_REGISTRY_URL}/registry/actors/did/{did}"
            )
    except HTTPException as http_err:
        if http_err.status_code == 404:
            bound_logger.info("Not valid issuer; DID not found on trust registry.")
            return False
        else:
            bound_logger.error(
                "Error retrieving actor from trust registry: `{}`.",
                http_err.detail,
            )
            raise http_err
    actor = actor_res.json()

    # We need role issuer
    if "roles" not in actor or "issuer" not in actor["roles"]:
        bound_logger.error("Actor `{}` does not have required role 'issuer'", actor)
        return False

    try:
        async with RichAsyncClient() as client:
            bound_logger.debug("Fetch schema from trust registry")
            await client.get(f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}")
    except HTTPException as http_err:
        if http_err.status_code == 404:
            bound_logger.info("Schema id not registered in trust registry.")
            return False
        else:
            bound_logger.error(
                "Something went wrong when fetching schema from trust registry: `{}`.",
                http_err.detail,
            )
            raise http_err

    bound_logger.info("Validated that DID and schema are on trust registry.")
    return True


async def accept_endorsement(client: AcaPyClient, endorsement: Endorsement):
    logger.debug("Endorsing transaction with id: `{}`", endorsement.transaction_id)
    await client.endorse_transaction.endorse_transaction(
        tran_id=endorsement.transaction_id
    )
