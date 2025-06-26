from sqlalchemy import ScalarResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.log_config import get_logger
from shared.models.trustregistry import Actor, Schema
from trustregistry import db

logger = get_logger(__name__)


async def get_actors(
    db_session: AsyncSession, skip: int = 0, limit: int = 1000
) -> list[db.Actor]:
    logger.info("Querying all actors from database (limit = {})", limit)

    query = select(db.Actor).offset(skip).limit(limit)
    result = await db_session.scalars(query)
    actors = result.all()

    if actors:
        num_rows = len(actors)
        logger.debug("Successfully retrieved `{}` actors from database.", num_rows)
        if num_rows == limit:
            logger.warning(
                "The number of actors returned is equal to limit used in the query."
            )
    else:
        logger.warning("No actors retrieved from database.")

    return list(actors)


async def get_actor_by_did(db_session: AsyncSession, actor_did: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_did": actor_did})
    bound_logger.info("Querying actor by DID")

    query = select(db.Actor).where(db.Actor.did == actor_did)
    result = await db_session.scalars(query)
    actor = result.first()

    if actor:
        bound_logger.debug("Successfully retrieved actor from database.")
    else:
        bound_logger.info("Actor DID not found.")
        raise ActorDoesNotExistError

    return actor


async def get_actor_by_id(db_session: AsyncSession, actor_id: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.info("Querying actor by ID")

    query = select(db.Actor).where(db.Actor.id == actor_id)
    result = await db_session.scalars(query)
    actor = result.first()

    if actor:
        bound_logger.debug("Successfully retrieved actor from database.")
    else:
        bound_logger.info("Actor ID not found.")
        raise ActorDoesNotExistError

    return actor


async def get_actor_by_name(db_session: AsyncSession, actor_name: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_name": actor_name})
    bound_logger.info("Query actor by name")

    query = select(db.Actor).where(db.Actor.name == actor_name)
    result = await db_session.scalars(query)
    actor = result.one_or_none()

    if actor:
        bound_logger.debug("Successfully retrieved actor from database")
    else:
        bound_logger.info("Actor name not found")
        raise ActorDoesNotExistError

    return actor


async def create_actor(db_session: AsyncSession, actor: Actor) -> db.Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.info("Try to create actor in database")

    try:
        bound_logger.debug("Adding actor to database")
        db_actor = db.Actor(**actor.model_dump())
        db_session.add(db_actor)
        await db_session.commit()
        await db_session.refresh(db_actor)

        bound_logger.debug("Successfully added actor to database.")
        return db_actor

    except IntegrityError as e:
        await db_session.rollback()
        constraint_violation = str(e.orig).lower()

        if "actors_pkey" in constraint_violation:
            bound_logger.info(
                "Bad request: An actor with ID already exists in database."
            )
            raise ActorAlreadyExistsError(
                f"Bad request: An actor with ID: `{actor.id}` already exists in database."
            ) from e

        elif "ix_actors_name" in constraint_violation:
            bound_logger.info(
                "Bad request: An actor with name already exists in database."
            )
            raise ActorAlreadyExistsError(
                f"Bad request: An actor with name: `{actor.name}` already exists in database."
            ) from e

        elif "ix_actors_didcomm_invitation" in constraint_violation:
            bound_logger.info(
                "Bad request: An actor with DIDComm invitation already exists in database."
            )
            raise ActorAlreadyExistsError(
                "Bad request: An actor with DIDComm invitation already exists in database."
            ) from e

        elif "ix_actors_did" in constraint_violation:
            bound_logger.info(
                "Bad request: An actor with DID already exists in database."
            )
            raise ActorAlreadyExistsError(
                f"Bad request: An actor with DID: `{actor.did}` already exists in database."
            ) from e

        else:
            bound_logger.error(
                "Unexpected constraint violation: {}", constraint_violation
            )
            raise ActorAlreadyExistsError(
                f"Bad request: Unique constraint violated - {constraint_violation}"
            ) from e

    except Exception as e:
        bound_logger.exception("Something went wrong during actor creation.")
        raise e


async def delete_actor(db_session: AsyncSession, actor_id: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.info("Delete actor from database. First assert actor ID exists")

    query = select(db.Actor).where(db.Actor.id == actor_id)
    result = await db_session.scalars(query)
    db_actor = result.one_or_none()

    if not db_actor:
        bound_logger.info("Requested actor ID to delete does not exist in database.")
        raise ActorDoesNotExistError

    bound_logger.debug("Deleting actor")
    query_delete = delete(db.Actor).where(db.Actor.id == actor_id)
    await db_session.execute(query_delete)
    await db_session.commit()

    bound_logger.debug("Successfully deleted actor ID.")
    return db_actor


async def update_actor(db_session: AsyncSession, actor: Actor) -> db.Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.info("Update actor in database. First assert actor ID exists")

    query = select(db.Actor).where(db.Actor.id == actor.id)
    result = await db_session.scalars(query)
    db_actor = result.one_or_none()

    if not db_actor:
        bound_logger.info("Requested actor ID to update does not exist in database.")
        raise ActorDoesNotExistError

    bound_logger.debug("Updating actor")
    update_query = (
        update(db.Actor)
        .where(db.Actor.id == actor.id)
        .values(
            name=actor.name,
            roles=actor.roles,
            didcomm_invitation=actor.didcomm_invitation,
            did=actor.did,
            image_url=actor.image_url if actor.image_url else db_actor.image_url,
        )
        .returning(db.Actor)
    )

    update_result: ScalarResult[db.Actor] = await db_session.scalars(update_query)
    await db_session.commit()

    updated_actor = update_result.first()

    if not updated_actor:  # pragma: no cover - should never happen
        bound_logger.error("Failed to update actor. Deleted before update complete?")
        raise ActorDoesNotExistError

    bound_logger.debug("Successfully updated actor.")
    return updated_actor


async def get_schemas(
    db_session: AsyncSession, skip: int = 0, limit: int = 1000
) -> list[db.Schema]:
    logger.info("Querying all schemas from database (limit = {})", limit)

    query = select(db.Schema).offset(skip).limit(limit)
    result = await db_session.scalars(query)
    schemas = result.all()

    if schemas:
        num_rows = len(schemas)
        logger.debug("Successfully retrieved `{}` schemas from database.", num_rows)
        if num_rows == limit:
            logger.warning(
                "The number of schemas returned is equal to limit used in the query."
            )
    else:
        logger.warning("No schemas retrieved from database.")

    return list(schemas)


async def get_schema_by_id(db_session: AsyncSession, schema_id: str) -> db.Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.info("Querying schema by ID")

    query = select(db.Schema).where(db.Schema.id == schema_id)
    result = await db_session.scalars(query)
    schema = result.first()

    if schema:
        bound_logger.debug("Successfully retrieved schema from database.")
    else:
        bound_logger.info("Schema ID not found.")
        raise SchemaDoesNotExistError

    return schema


async def create_schema(db_session: AsyncSession, schema: Schema) -> db.Schema:
    bound_logger = logger.bind(body={"schema": schema})
    bound_logger.info("Try to create schema in database")

    try:
        bound_logger.debug("Adding schema to database")
        db_schema = db.Schema(**schema.model_dump())
        db_session.add(db_schema)
        await db_session.commit()
        await db_session.refresh(db_schema)

        bound_logger.debug("Successfully added schema to database.")
        return db_schema

    except IntegrityError as e:
        await db_session.rollback()
        bound_logger.info(
            "Bad request: Schema already exists in database. {}", str(e.orig).lower()
        )
        raise SchemaAlreadyExistsError from e

    except Exception as e:
        bound_logger.exception("Something went wrong during schema creation.")
        raise e


async def update_schema(
    db_session: AsyncSession, schema: Schema, schema_id: str
) -> db.Schema:
    bound_logger = logger.bind(body={"schema": schema, "schema_id": schema_id})
    bound_logger.info("Update schema in database. First assert schema ID exists")

    query = select(db.Schema).where(db.Schema.id == schema_id)
    result = await db_session.scalars(query)
    db_schema = result.one_or_none()

    if not db_schema:
        bound_logger.info("Requested schema ID to update does not exist in database.")
        raise SchemaDoesNotExistError

    bound_logger.debug("Updating schema")
    update_query = (
        update(db.Schema)
        .where(db.Schema.id == schema_id)
        .values(
            did=schema.did,
            name=schema.name,
            version=schema.version,
        )
        .returning(db.Schema)
    )

    update_result: ScalarResult[db.Schema] = await db_session.scalars(update_query)
    await db_session.commit()

    updated_schema = update_result.first()

    if not updated_schema:  # pragma: no cover - should never happen
        bound_logger.error("Failed to update schema. Deleted before update complete?")
        raise SchemaDoesNotExistError

    bound_logger.debug("Successfully updated schema.")
    return updated_schema


async def delete_schema(db_session: AsyncSession, schema_id: str) -> db.Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.info("Delete schema from database. First assert schema ID exists")

    query = select(db.Schema).where(db.Schema.id == schema_id)
    result = await db_session.scalars(query)
    db_schema = result.one_or_none()

    if not db_schema:
        bound_logger.info("Requested schema ID to delete does not exist in database.")
        raise SchemaDoesNotExistError

    bound_logger.debug("Deleting schema")
    query_delete = delete(db.Schema).where(db.Schema.id == schema_id)
    await db_session.execute(query_delete)
    await db_session.commit()

    bound_logger.debug("Successfully deleted schema ID.")
    return db_schema


# Exception classes
class ActorAlreadyExistsError(Exception):
    """Raised when attempting to create an actor that already exists in the database."""


class ActorDoesNotExistError(Exception):
    """Raised when attempting to delete or update an actor that does not exist in the database."""


class SchemaAlreadyExistsError(Exception):
    """Raised when attempting to create a schema that already exists in the database."""


class SchemaDoesNotExistError(Exception):
    """Raised when attempting to delete or update a schema that does not exist in the database."""
