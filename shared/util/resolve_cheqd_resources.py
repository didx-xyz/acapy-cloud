from fastapi import HTTPException

from shared.constants import RESOLVER_URL
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


client = RichAsyncClient()


async def resolve_cheqd_schema(schema_id: str) -> dict | None:
    """Resolve a Cheqd schema by its ID.

    Parameters
    ----------
    schema_id : str
        The ID of the schema to resolve.

    Returns
    -------
    dict: The resolved schema.

    """
    try:
        logger.debug(f"Resolving Cheqd schema with schema_id: {schema_id}")
        response = await client.get(f"{RESOLVER_URL}/{schema_id}")

    except HTTPException as e:
        logger.error(
            f"HTTPException while resolving schema with schema_id {schema_id}: {e.detail}"
        )
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error while resolving schema with schema_id {schema_id}: {e!s}"
        )
        raise HTTPException(status_code=500, detail="Internal Server Error") from e

    return response.json()
