from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.log_config import get_logger
from shared.models.trustregistry import Actor
from trustregistry import crud
from trustregistry.db import get_async_db

logger = get_logger(__name__)

router = APIRouter(prefix="/registry/actors", tags=["actor"])


@router.get("")
async def get_actors(db_session: AsyncSession = Depends(get_async_db)) -> list[Actor]:
    logger.debug("GET request received: Fetch all actors")
    db_actors = await crud.get_actors(db_session)

    # Convert database models to pydantic models
    result = [Actor(**actor.__dict__) for actor in db_actors]
    return result


@router.post("")
async def register_actor(
    actor: Actor, db_session: AsyncSession = Depends(get_async_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.debug("POST request received: Register actor")
    try:
        created_actor = await crud.create_actor(db_session, actor=actor)
    except crud.ActorAlreadyExistsError as e:
        bound_logger.info("Bad request: Actor already exists.")
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        bound_logger.error("Something went wrong during actor creation.")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return created_actor


@router.put("/{actor_id}")
async def update_actor(
    actor_id: str, actor: Actor, db_session: AsyncSession = Depends(get_async_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id, "actor": actor})
    bound_logger.debug("PUT request received: Update actor")
    if actor.id and actor.id != actor_id:
        bound_logger.info("Bad request: Actor ID in request doesn't match ID in URL.")
        raise HTTPException(
            status_code=400,
            detail=f"The provided actor ID '{actor.id}' in the request body "
            f"does not match the actor ID '{actor_id}' in the URL.",
        )
    if not actor.id:
        actor.id = actor_id

    try:
        update_actor_result = await crud.update_actor(db_session, actor=actor)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e

    return update_actor_result


@router.get("/did/{actor_did}")
async def get_actor_by_did(
    actor_did: str, db_session: AsyncSession = Depends(get_async_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_did": actor_did})
    bound_logger.debug("GET request received: Get actor by DID")
    try:
        actor = await crud.get_actor_by_did(db_session, actor_did=actor_did)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with did not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with did {actor_did} not found."
        ) from e

    return actor


@router.get("/{actor_id}")
async def get_actor_by_id(
    actor_id: str, db_session: AsyncSession = Depends(get_async_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.debug("GET request received: Get actor by ID")
    try:
        actor = await crud.get_actor_by_id(db_session, actor_id=actor_id)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e

    return actor


@router.get("/name/{actor_name}")
async def get_actor_by_name(
    actor_name: str, db_session: AsyncSession = Depends(get_async_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_name": actor_name})
    bound_logger.debug("GET request received: Get actor by name")
    try:
        actor = await crud.get_actor_by_name(db_session, actor_name=actor_name)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with name not found")
        raise HTTPException(
            status_code=404, detail=f"Actor with name {actor_name} not found"
        ) from e

    return actor


@router.delete("/{actor_id}", status_code=204)
async def remove_actor(
    actor_id: str, db_session: AsyncSession = Depends(get_async_db)
) -> None:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.debug("DELETE request received: Delete actor by ID")
    try:
        await crud.delete_actor(db_session, actor_id=actor_id)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e
