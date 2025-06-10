from app.exceptions import TrustRegistryException
from app.services.trust_registry.actors import fetch_actor_by_id
from shared.constants import TRUST_REGISTRY_URL
from shared.log_config import get_logger
from shared.models.trustregistry import TrustRegistryRole
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


async def actor_has_role(actor_id: str, role: TrustRegistryRole) -> bool:
    """Check whether the actor has specified role.

    Args:
        actor_id (str): identifier of the actor to check the role for
        role (Role): role of the actor

    Returns:
        bool: Whether the actor with specified id has specified role

    """
    bound_logger = logger.bind(body={"actor_id": actor_id, "role": role})
    bound_logger.debug("Asserting actor has role")
    actor = await fetch_actor_by_id(actor_id)

    if not actor:
        bound_logger.info("Actor not registered in trust registry.")
        raise TrustRegistryException(f"Actor with id {actor_id} not found.", 404)

    result = role in actor.roles
    if result:
        bound_logger.debug("Actor has requested role.")
    else:
        bound_logger.debug("Actor does not have requested role.")
    return result


async def assert_actor_name(actor_name: str) -> bool:
    """Assert if actor name exists in trust registry

    Args:
        actor_name (str): name of the actor to retrieve

    Raises:
        TrustRegistryException: If an error occurred while retrieving the actor.

    Returns:
        Bool: if actor exists

    """
    bound_logger = logger.bind(body={"actor_name": actor_name})
    bound_logger.debug("Fetching actor by name from trust registry")

    async with RichAsyncClient(raise_status_error=False) as client:
        actor_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/name/{actor_name}"
        )

    if actor_response.status_code == 404:
        return False
    elif actor_response.is_error:
        bound_logger.error(
            "Error fetching actor by name. Got status code {} with message `{}`.",
            actor_response.status_code,
            actor_response.text,
        )
        raise TrustRegistryException(
            f"Error fetching actor by name: `{actor_response.text}`",
            actor_response.status_code,
        )

    bound_logger.debug("Asserted actor name is in trust registry.")
    return True
