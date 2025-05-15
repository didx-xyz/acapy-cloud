from fastapi import HTTPException

from shared.constants import TRUST_REGISTRY_URL
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


async def registry_has_schema(schema_id: str) -> bool:
    """Check whether the trust registry has a schema registered

    Args:
        schema_id (str): the schema id to check

    Raises:
        TrustRegistryException: If an error occurred while retrieving the schemas

    Returns:
        bool: whether the schema exists in the trust registry
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug(
        "Asserting if schema is registered. Fetching schema by ID from trust registry"
    )
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
                "Something went wrong when fetching schema from trust registry."
            )
            raise http_err

    bound_logger.debug("Schema exists in registry.")
    return True
