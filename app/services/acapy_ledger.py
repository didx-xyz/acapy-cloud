from typing import Literal, Optional, Tuple

from aiocache import SimpleMemoryCache, cached
from aries_cloudcontroller import (
    AcaPyClient,
    GetDIDEndpointResponse,
    GetSchemaResult,
    SchemaGetResult,
    TAAAccept,
    TAAInfo,
    TAARecord,
    TxnOrRegisterLedgerNymResponse,
)

from app.exceptions import CloudApiException, handle_acapy_call
from shared.log_config import get_logger

logger = get_logger(__name__)


async def get_taa(controller: AcaPyClient) -> Tuple[TAAInfo, str]:
    """
    Obtains the TAA from the ledger

    Parameters:
    -----------
    controller: AcaPyClient
        The aries_cloudcontroller object

    Returns:
    --------
    taa: Tuple[TAAInfo, str]
        The TAAInfo object, with the mechanism
    """
    logger.debug("Fetching TAA")
    taa_response = await handle_acapy_call(
        logger=logger, acapy_call=controller.ledger.fetch_taa
    )

    taa_info = taa_response.result
    if not taa_info or (not taa_info.taa_record and taa_info.taa_required):
        logger.error("Failed to get TAA. Received info: `{}`.", taa_info)
        raise CloudApiException("Something went wrong. Could not get TAA.")

    logger.debug("Successfully fetched TAA info: {}", taa_info)
    mechanism = (
        taa_info.taa_accepted.mechanism
        if taa_info.taa_accepted
        else "service_agreement"
    )
    return taa_info, mechanism


async def accept_taa(
    controller: AcaPyClient, taa: TAARecord, mechanism: Optional[str] = None
) -> None:
    """
    Accept the TAA

    Parameters:
    -----------
    controller: AcaPyClient
        The aries_cloudcontroller object
    TAA:
        The TAA object we want to agree to
    mechanism:
        An optional mechanism to specify
    """
    logger.bind(body=taa).debug("Accepting TAA")
    request_body = TAAAccept(**taa.to_dict(), mechanism=mechanism)
    try:
        await handle_acapy_call(
            logger=logger, acapy_call=controller.ledger.accept_taa, body=request_body
        )
    except CloudApiException as e:
        logger.error("An exception occurred while trying to accept TAA.")
        raise CloudApiException(
            f"An unexpected error occurred while trying to accept TAA: {e.detail}"
        ) from e

    logger.debug("Successfully accepted TAA.")


async def get_did_endpoint(
    controller: AcaPyClient, issuer_nym: str
) -> GetDIDEndpointResponse:
    """
    Obtains the public DID endpoint

    Parameters:
    -----------
    controller: AcaPyClient
        The aries_cloudcontroller object
    issuer_nym: str
        The issuer's Verinym

    Returns:
    --------
    GetDIDEndpointResponse
        The response from getting the public endpoint associated with
        the issuer's Verinym from the ledger
    """
    bound_logger = logger.bind(body={"issuer_nym": issuer_nym})
    bound_logger.debug("Fetching DID endpoint")

    issuer_endpoint_response = await handle_acapy_call(
        logger=logger, acapy_call=controller.ledger.get_did_endpoint, did=issuer_nym
    )
    if not issuer_endpoint_response:
        bound_logger.info("Failed to get DID endpoint; received empty response.")
        raise CloudApiException("Could not obtain issuer endpoint.", 404)
    bound_logger.debug("Successfully fetched DID endpoint.")
    return issuer_endpoint_response


async def register_nym_on_ledger(
    aries_controller: AcaPyClient,
    *,
    did: str,
    verkey: str,
    alias: Optional[str] = None,
    role: Optional[str] = None,
    connection_id: Optional[str] = None,
    create_transaction_for_endorser: Optional[str] = None,
) -> TxnOrRegisterLedgerNymResponse:
    bound_logger = logger.bind(body={"did": did})
    bound_logger.info("Registering NYM on ledger")
    try:
        response = await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.ledger.register_nym,
            did=did,
            verkey=verkey,
            alias=alias,
            role=role,
            conn_id=connection_id,
            create_transaction_for_endorser=create_transaction_for_endorser,
        )
        bound_logger.debug("Successfully registered NYM on ledger.")
        return response
    except CloudApiException as e:
        raise CloudApiException(
            f"Error registering NYM on ledger: {e.detail}", e.status_code
        ) from e


async def accept_taa_if_required(aries_controller: AcaPyClient) -> None:
    taa_response, mechanism = await get_taa(aries_controller)

    if taa_response.taa_required:
        await accept_taa(
            controller=aries_controller,
            taa=taa_response.taa_record,
            mechanism=mechanism,
        )


# Use the cred_def_id from args as cache-key
# The function itself is at args[0], so args[2] refers to cred_def_id
@cached(cache=SimpleMemoryCache, key_builder=lambda *args: args[2])
async def schema_id_from_credential_definition_id(
    controller: AcaPyClient,
    credential_definition_id: str,
    wallet_type: Literal["askar", "askar-anoncreds"],
) -> str:
    """
    From a credential definition, get the identifier for its schema.

    Taken from ACA-Py implementation:
    https://github.com/openwallet-foundation/acapy/blob/f9506df755e46c5be93b228c8811276b743a1adc/aries_cloudagent/ledger/indy.py#L790

    Parameters:
    ----------
    controller: AcaPyClient
        The aries_cloudcontroller object
    credential_definition_id: The identifier of the credential definition
            from which to identify a schema

    Returns:
    -------
    schema_id : string
    """
    bound_logger = logger.bind(
        body={"credential_definition_id": credential_definition_id}
    )
    bound_logger.debug("Getting schema id from credential definition id")

    if credential_definition_id.startswith("did:cheqd"):
        # TODO: Implement schema id retrieval for Cheqd
        return ""

    # scrape schema id or sequence number from cred def id
    tokens = credential_definition_id.split(":")
    if len(tokens) == 8:  # node protocol >= 1.4: cred def id has 5 or 8 tokens
        bound_logger.debug("Constructed schema id from credential definition.")
        return ":".join(tokens[3:7])  # schema id spans 0-based positions 3-6

    # get txn by sequence number, retrieve schema identifier components
    seq_no = tokens[3]

    bound_logger.debug("Fetching schema using sequence number: `{}`", seq_no)
    if wallet_type == "askar":
        schema_indy: SchemaGetResult = await handle_acapy_call(
            logger=logger,
            acapy_call=controller.schema.get_schema,
            schema_id=seq_no,
        )
        if not schema_indy.var_schema or not schema_indy.var_schema.id:
            bound_logger.warning("No schema found with sequence number: `{}`.", seq_no)
            raise CloudApiException(f"Schema with id {seq_no} not found.", 404)
        schema_id = schema_indy.var_schema.id

    else:  # wallet_type == "askar-anoncreds"
        schema: GetSchemaResult = await handle_acapy_call(
            logger=logger,
            acapy_call=controller.anoncreds_schemas.get_schema,
            schema_id=seq_no,
        )

        if not schema.schema_id:
            bound_logger.warning("No schema found with sequence number: `{}`.", seq_no)
            raise CloudApiException(f"Schema with id {seq_no} not found.", 404)
        schema_id = schema.schema_id

    bound_logger.debug("Successfully obtained schema id from credential definition.")
    return schema_id
