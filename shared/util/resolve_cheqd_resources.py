from typing import Optional

from fastapi import HTTPException

from shared.constants import RESOLVER_URL
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


client = RichAsyncClient()


async def resolve_cheqd_schema(id: str) -> Optional[dict]:
    """
    Resolve a Cheqd schema by its ID.

    Parameters:
    id (str): The ID of the schema to resolve.

    Returns:
    dict: The resolved schema.
    """

    try:
        logger.debug(f"Resolving Cheqd schema with id: {id}")
        response = await client.get(f"{RESOLVER_URL}/{id}")

    except HTTPException as e:
        logger.error(f"HTTPException while resolving schema with id {id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error while resolving schema with id {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response.json()
