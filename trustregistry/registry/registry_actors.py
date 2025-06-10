from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from shared.log_config import get_logger
from shared.models.trustregistry import Actor
from trustregistry import crud
from trustregistry.db import get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/registry/actors", tags=["actor"])


@router.get("", response_model=list[Actor])
async def get_actors(db_session: Session = Depends(get_db)) -> list[Actor]:
    logger.debug("GET request received: Fetch all actors")
    db_actors = crud.get_actors(db_session)

    return db_actors


@router.post("", response_model=Actor)
async def register_actor(actor: Actor, db_session: Session = Depends(get_db)) -> Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.debug("POST request received: Register actor")
    try:
        created_actor = crud.create_actor(db_session, actor=actor)
    except crud.ActorAlreadyExistsError as e:
        bound_logger.info("Bad request: Actor already exists.")
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        bound_logger.error("Something went wrong during actor creation.")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return created_actor


@router.put("/{actor_id}", response_model=Actor)
async def update_actor(
    actor_id: str, actor: Actor, db_session: Session = Depends(get_db)
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
        update_actor_result = crud.update_actor(db_session, actor=actor)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e

    return update_actor_result


@router.get("/did/{actor_did}", response_model=Actor)
async def get_actor_by_did(
    actor_did: str, db_session: Session = Depends(get_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_did": actor_did})
    bound_logger.debug("GET request received: Get actor by DID")
    try:
        actor = crud.get_actor_by_did(db_session, actor_did=actor_did)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with did not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with did {actor_did} not found."
        ) from e

    return actor


@router.get("/{actor_id}", response_model=Actor)
async def get_actor_by_id(
    actor_id: str, db_session: Session = Depends(get_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.debug("GET request received: Get actor by ID")
    try:
        actor = crud.get_actor_by_id(db_session, actor_id=actor_id)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e

    return actor


@router.get("/name/{actor_name}", response_model=Actor)
async def get_actor_by_name(
    actor_name: str, db_session: Session = Depends(get_db)
) -> Actor:
    bound_logger = logger.bind(body={"actor_name": actor_name})
    bound_logger.debug("GET request received: Get actor by name")
    try:
        actor = crud.get_actor_by_name(db_session, actor_name=actor_name)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with name not found")
        raise HTTPException(
            status_code=404, detail=f"Actor with name {actor_name} not found"
        ) from e

    return actor


@router.delete("/{actor_id}", status_code=204)
async def remove_actor(actor_id: str, db_session: Session = Depends(get_db)) -> None:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.debug("DELETE request received: Delete actor by ID")
    try:
        crud.delete_actor(db_session, actor_id=actor_id)
    except crud.ActorDoesNotExistError as e:
        bound_logger.info("Bad request: Actor with id not found.")
        raise HTTPException(
            status_code=404, detail=f"Actor with id {actor_id} not found."
        ) from e
