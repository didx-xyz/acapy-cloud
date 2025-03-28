from typing import List, Literal, Optional

from fastapi import HTTPException

from app.exceptions import TrustRegistryException
from shared.constants import TRUST_REGISTRY_URL
from shared.log_config import get_logger
from shared.models.trustregistry import Schema
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


async def register_schema(
    schema_id: str, schema_type: Literal["indy", "anoncreds"]
) -> None:
    """Register a schema in the trust registry

    Args:
        schema_id (str): the schema id to register

    Raises:
        TrustRegistryException: If an error occurred while registering the schema
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("Registering schema on trust registry")
    async with RichAsyncClient() as client:
        try:
            await client.post(
                f"{TRUST_REGISTRY_URL}/registry/schemas",
                json={"schema_id": schema_id, "schema_type": schema_type},
            )
        except HTTPException as e:
            bound_logger.error(
                "Error registering schema. Got status code {} with message `{}`.",
                e.status_code,
                e.detail,
            )
            raise TrustRegistryException(
                f"Error registering schema `{schema_id}`. Error: `{e.detail}`.",
                e.status_code,
            ) from e

    bound_logger.debug("Successfully registered schema on trust registry.")


async def fetch_schemas() -> List[Schema]:
    """Retrieve all schemas from the trust registry

    Raises:
        TrustRegistryException: If an error occurred while retrieving the trust registry schemas.

    Returns:
        A list of schemas
    """
    logger.debug("Fetching all schemas from trust registry")
    async with RichAsyncClient() as client:
        try:
            schemas_res = await client.get(f"{TRUST_REGISTRY_URL}/registry/schemas")
        except HTTPException as e:
            logger.error(
                "Error fetching schemas. Got status code {} with message `{}`.",
                e.status_code,
                e.detail,
            )
            raise TrustRegistryException(
                f"Unable to fetch schemas: `{e.detail}`.", e.status_code
            ) from e

    result = [Schema.model_validate(schema) for schema in schemas_res.json()]
    logger.debug("Successfully fetched schemas from trust registry.")
    return result


async def get_schema_by_id(schema_id: str) -> Optional[Schema]:
    """Retrieve a schemas from the trust registry

    Raises:
        TrustRegistryException: If an error occurred while retrieving the trust registry schemas.

    Returns:
        A schema
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("Fetching schema from trust registry")

    async with RichAsyncClient() as client:
        try:
            schema_response = await client.get(
                f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}"
            )
        except HTTPException as e:
            if e.status_code == 404:
                bound_logger.info("Bad request: Schema with id not found.")
                return None
            else:
                bound_logger.error(
                    "Error fetching schema. Got status code {} with message `{}`.",
                    e.status_code,
                    e.detail,
                )
                raise TrustRegistryException(
                    f"Unable to fetch schema: `{e.detail}`.",
                    e.status_code,
                ) from e

    result = Schema.model_validate(schema_response.json())
    logger.debug("Successfully fetched schema from trust registry.")
    return result


async def remove_schema_by_id(schema_id: str) -> None:
    """Remove schema from trust registry by id

    Args:
        actor_id (str): identifier of the schema to remove

    Raises:
        TrustRegistryException: If an error occurred while removing the schema
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.info("Removing schema from trust registry")
    async with RichAsyncClient() as client:
        try:
            await client.delete(f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}")
        except HTTPException as e:
            bound_logger.error(
                "Error removing schema. Got status code {} with message `{}`.",
                e.status_code,
                e.detail,
            )
            raise TrustRegistryException(
                f"Error removing schema from trust registry: `{e.detail}`.",
                e.status_code,
            ) from e

    bound_logger.debug("Successfully removed schema from trust registry.")
