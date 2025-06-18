from aiocache import SimpleMemoryCache, cached
from aries_cloudcontroller import AcaPyClient, GetSchemaResult

from app.exceptions import CloudApiException, handle_acapy_call
from shared.log_config import get_logger

logger = get_logger(__name__)


# Use the cred_def_id from args as cache-key
# The function itself is at args[0], so args[2] refers to cred_def_id
@cached(cache=SimpleMemoryCache, key_builder=lambda *args: args[2])
async def schema_id_from_credential_definition_id(
    controller: AcaPyClient,
    credential_definition_id: str,
) -> str:
    """From a credential definition, get the identifier for its schema.

    Taken from ACA-Py implementation:
    https://github.com/openwallet-foundation/acapy/blob/f9506df755e46c5be93b228c8811276b743a1adc/aries_cloudagent/ledger/indy.py#L790

    Parameters
    ----------
    controller: AcaPyClient
        The aries_cloudcontroller object
    credential_definition_id: The identifier of the credential definition
            from which to identify a schema

    Returns
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
