from fastapi import HTTPException

from shared import TRUST_REGISTRY_URL
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


async def is_valid_issuer(did: str, schema_id: str) -> bool:
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
