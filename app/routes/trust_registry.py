from typing import List, Optional

from fastapi import APIRouter, HTTPException

import app.services.trust_registry.actors as registry_actors
import app.services.trust_registry.schemas as registry_schemas
from shared.log_config import get_logger
from shared.models.trustregistry import Actor, Schema

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/trust-registry", tags=["trust-registry"])


@router.get("/schemas", response_model=List[Schema])
async def get_schemas() -> List[Schema]:
    """
    Fetch the schemas from the trust registry.

    Returns:
    ---------
    Only the schemas from the trust registry
    """
    logger.debug("GET request received: Fetch schemas from the trust registry")
    schemas = await registry_schemas.fetch_schemas()

    logger.debug("Successfully retrieved schemas.")
    return schemas


@router.get("/schemas/{schema_id:path}", response_model=Schema)
async def get_schema_by_id(schema_id: str) -> Schema:
    """
    Retrieve schema by id.

    Parameters:
    -----------
    schema_id: str

    Returns:
    -----------
    A schema from the trust registry
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("GET request received: Fetch schema by id")
    schema = await registry_schemas.get_schema_by_id(schema_id)

    if schema:
        bound_logger.debug("Successfully fetched schema by id.")
        return schema
    else:
        bound_logger.info("Bad request: schema with id not found.")
        raise HTTPException(404, f"Schema with id: {schema_id} not found")


@router.get("/actors", response_model=List[Actor])
async def get_actors(
    actor_did: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
) -> List[Actor]:
    """
    Fetch all actors from the trust registry.
    Alternatively, provide one of: did, id, or name, to fetch corresponding actor.

    Parameters:
    -----------
    actor_did: str (Optional) - DID of the Actor

    actor_id: str (Optional) - Wallet ID of the Actor

    actor_name: str (Optional) - Alias of the Actor

    Returns:
    ---------
    All actors from the trust registry, or one actor if a query parameter is passed
    """
    param_count = sum(1 for var in [actor_did, actor_name, actor_id] if var)

    if param_count == 0:
        logger.debug("GET request received: Fetch all actors from the trust registry")
        actors = await registry_actors.fetch_all_actors()

        logger.debug("Successfully retrieved actors.")
        return actors

    bound_logger = logger.bind(
        body={"actor_did": actor_did, "actor_id": actor_id, "actor_name": actor_name}
    )
    bound_logger.debug("GET request received: Fetch actor by query param")

    if param_count > 1:
        bound_logger.info("Bad request, more than one query param provided.")
        raise HTTPException(
            400,
            "Bad request: More than one query parameter provided when max 1 expected",
        )

    # One query param provided:
    if actor_did:
        bound_logger.debug(
            "GET request received: Fetch actor by did from the trust registry"
        )
        actor = await registry_actors.fetch_actor_by_did(actor_did)
    elif actor_id:
        bound_logger.debug(
            "GET request received: Fetch actor by id from the trust registry"
        )
        actor = await registry_actors.fetch_actor_by_id(actor_id)
    else:  # actor_name
        bound_logger.debug(
            "GET request received: Fetch actor by name from the trust registry"
        )
        actor = await registry_actors.fetch_actor_by_name(actor_name)

    if actor:
        bound_logger.debug("Successfully retrieved actor.")
        return [actor]
    else:
        bound_logger.info("Bad request: actor not found.")
        raise HTTPException(404, "Actor not found")


@router.get("/actors/issuers", response_model=List[Actor])
async def get_issuers() -> List[Actor]:
    """
    Fetch the issuers from the trust registry.

    Returns:
    ---------
    List of issuer actors
    """
    logger.debug("GET request received: Fetch the issuers from the trust registry")
    issuers = await registry_actors.fetch_actors_with_role("issuer")

    logger.debug("Successfully retrieved issuers.")
    return issuers


@router.get("/actors/verifiers", response_model=List[Actor])
async def get_verifiers() -> List[Actor]:
    """
    Fetch the verifiers from the trust registry.

    Returns:
    ---------
    List of verifier actors
    """
    logger.debug("GET request received: Fetch the verifiers from the trust registry")
    verifiers = await registry_actors.fetch_actors_with_role("verifier")

    logger.debug("Successfully retrieved verifiers.")
    return verifiers
