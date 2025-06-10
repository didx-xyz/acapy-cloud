from app.exceptions import TrustRegistryException
from app.services.trust_registry.actors import fetch_actor_by_did
from app.services.trust_registry.util.schema import registry_has_schema
from shared.log_config import get_logger

logger = get_logger(__name__)


async def assert_valid_issuer(did: str, schema_id: str | None = None) -> None:
    """Assert that an actor with the specified did is registered as issuer.

    This method asserts that there is an actor registered in the trust registry
    with the specified did. It verifies whether this actor has the `issuer` role
    and will also make sure the specified schema_id is registered as a valid schema.
    Raises an exception if one of the assertions fail.

    NOTE: the dids in the registry are registered as fully qualified dids. This means
    when passing a did to this method it must also be fully qualified (e.g. `did:sov:xxxx`)

    Args:
        did (str): the did of the issuer in fully qualified format.
        schema_id (Optional[str]): the schema_id of the credential being issued (Optional).

    Raises:
        Exception: When the did is not registered, the actor doesn't have the issuer role
            or the schema is not registered in the registry.

    """
    bound_logger = logger.bind(body={"did": did, "schema_id": schema_id})
    bound_logger.debug("Asserting issuer DID and schema_id is registered")
    actor = await fetch_actor_by_did(did)

    if not actor:
        bound_logger.info("DID not registered in the trust registry.")
        raise TrustRegistryException(f"DID {did} not registered in the trust registry.")

    if "issuer" not in actor.roles:
        bound_logger.info("Actor associated with DID does not have `issuer` role.")
        raise TrustRegistryException(
            f"Actor {actor.id} does not have required role 'issuer'."
        )
    bound_logger.debug("Issuer DID is valid")

    if schema_id:
        has_schema = await registry_has_schema(schema_id)
        if not has_schema:
            bound_logger.info("Schema is not registered in the trust registry.")
            raise TrustRegistryException(
                f"Schema with id {schema_id} is not registered in trust registry."
            )
        bound_logger.debug("Schema ID is registered.")
