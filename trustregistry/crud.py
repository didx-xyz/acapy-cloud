from sqlalchemy import ScalarResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.log_config import get_logger
from shared.models.trustregistry import Actor, Schema
from trustregistry import db

logger = get_logger(__name__)


def get_actors(db_session: Session, skip: int = 0, limit: int = 1000) -> list[db.Actor]:
    logger.info("Querying all actors from database (limit = {})", limit)

    query = select(db.Actor).offset(skip).limit(limit)
    result = db_session.scalars(query).all()

    if result:
        num_rows = len(result)
        logger.debug("Successfully retrieved `{}` actors from database.", num_rows)
        if num_rows == limit:
            logger.warning(
                "The number of actors returned is equal to limit used in the query."
            )
    else:
        logger.warning("No actors retrieved from database.")

    return result


def get_actor_by_did(db_session: Session, actor_did: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_did": actor_did})
    bound_logger.info("Querying actor by DID")

    query = select(db.Actor).where(db.Actor.did == actor_did)
    result = db_session.scalars(query).first()

    if result:
        bound_logger.debug("Successfully retrieved actor from database.")
    else:
        bound_logger.info("Actor DID not found.")
        raise ActorDoesNotExistError

    return result


def get_actor_by_id(db_session: Session, actor_id: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.info("Querying actor by ID")

    query = select(db.Actor).where(db.Actor.id == actor_id)
    result = db_session.scalars(query).first()

    if result:
        bound_logger.debug("Successfully retrieved actor from database.")
    else:
        bound_logger.info("Actor ID not found.")
        raise ActorDoesNotExistError

    return result


def get_actor_by_name(db_session: Session, actor_name: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_name": actor_name})
    bound_logger.info("Query actor by name")

    query = select(db.Actor).where(db.Actor.name == actor_name)
    result = db_session.scalars(query).one_or_none()

    if result:
        bound_logger.debug("Successfully retrieved actor from database")
    else:
        bound_logger.info("Actor name not found")
        raise ActorDoesNotExistError

    return result


def create_actor(db_session: Session, actor: Actor) -> db.Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.info("Try to create actor in database")

    try:
        bound_logger.debug("Adding actor to database")
        db_actor = db.Actor(**actor.model_dump())
        db_session.add(db_actor)
        db_session.commit()
        db_session.refresh(db_actor)

        bound_logger.debug("Successfully added actor to database.")
        return db_actor

    except IntegrityError as e:
        db_session.rollback()
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


def delete_actor(db_session: Session, actor_id: str) -> db.Actor:
    bound_logger = logger.bind(body={"actor_id": actor_id})
    bound_logger.info("Delete actor from database. First assert actor ID exists")

    query = select(db.Actor).where(db.Actor.id == actor_id)
    db_actor = db_session.scalars(query).one_or_none()

    if not db_actor:
        bound_logger.info("Requested actor ID to delete does not exist in database.")
        raise ActorDoesNotExistError

    bound_logger.debug("Deleting actor")
    query_delete = delete(db.Actor).where(db.Actor.id == actor_id)
    db_session.execute(query_delete)
    db_session.commit()

    bound_logger.debug("Successfully deleted actor ID.")
    return db_actor


def update_actor(db_session: Session, actor: Actor) -> db.Actor:
    bound_logger = logger.bind(body={"actor": actor})
    bound_logger.info("Update actor in database. First assert actor ID exists")

    query = select(db.Actor).where(db.Actor.id == actor.id)
    db_actor = db_session.scalars(query).one_or_none()

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

    result: ScalarResult[db.Actor] = db_session.scalars(update_query)
    db_session.commit()

    updated_actor = result.first()

    bound_logger.debug("Successfully updated actor.")
    return updated_actor


def get_schemas(
    db_session: Session, skip: int = 0, limit: int = 1000
) -> list[db.Schema]:
    logger.debug("Query all schemas from database (limit = {})", limit)
    query = select(db.Schema).offset(skip).limit(limit)
    result = db_session.scalars(query).all()

    if result:
        num_rows = len(result)
        logger.debug("Successfully retrieved {} schemas from database.", num_rows)
        if num_rows == limit:
            logger.warning(
                "The number of schemas returned is equal to limit used in the query."
            )
    else:
        logger.warning("No schemas retrieved from database.")

    return result


def get_schema_by_id(db_session: Session, schema_id: str) -> db.Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.info("Querying for schema by ID")

    query = select(db.Schema).where(db.Schema.id == schema_id)
    result = db_session.scalars(query).first()

    if not result:
        bound_logger.info("Schema does not exist in database.")
        raise SchemaDoesNotExistError

    return result


def create_schema(db_session: Session, schema: Schema) -> db.Schema:
    bound_logger = logger.bind(body={"schema": schema})
    bound_logger.info(
        "Create schema in database. First assert schema ID does not already exist"
    )

    query = select(db.Schema).where(db.Schema.id == schema.id)
    db_schema = db_session.scalars(query).one_or_none()

    if db_schema:
        bound_logger.info("The requested schema ID already exists in database.")
        raise SchemaAlreadyExistsError

    bound_logger.debug("Adding schema to database")

    db_schema = db.Schema(**schema.model_dump())
    db_session.add(db_schema)
    db_session.commit()
    db_session.refresh(db_schema)

    bound_logger.debug("Successfully added schema to database.")
    return db_schema


def update_schema(db_session: Session, schema: Schema, schema_id: str) -> db.Schema:
    bound_logger = logger.bind(body={"schema": schema, "schema_id": schema_id})
    bound_logger.info("Update schema in database. First assert schema ID exists")

    query = select(db.Schema).where(db.Schema.id == schema_id)
    db_schema = db_session.scalars(query).one_or_none()

    if not db_schema:
        bound_logger.debug(
            "Requested to update a schema that does not exist in database."
        )
        raise SchemaDoesNotExistError

    bound_logger.debug("Updating schema on database")

    update_query = (
        update(db.Schema)
        .where(db.Schema.id == schema_id)
        .values(id=schema.id, name=schema.name, version=schema.version, did=schema.did)
        .returning(db.Schema)
    )

    result: ScalarResult[db.Schema] = db_session.scalars(update_query)
    db_session.commit()

    updated_schema = result.first()

    bound_logger.debug("Successfully updated schema on database.")
    return updated_schema


def delete_schema(db_session: Session, schema_id: str) -> db.Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.info("Delete schema from database. First assert schema ID exists")

    query_does_exists = select(db.Schema).where(db.Schema.id == schema_id)
    db_schema = db_session.scalars(query_does_exists).one_or_none()

    if not db_schema:
        raise SchemaDoesNotExistError

    query_delete = delete(db.Schema).where(db.Schema.id == schema_id)
    bound_logger.debug("Deleting schema from database")
    db_session.execute(query_delete)
    db_session.commit()

    bound_logger.debug("Successfully deleted schema from database.")
    return db_schema


class ActorAlreadyExistsError(Exception):
    """Raised when attempting to create an actor that already exists in the database."""


class ActorDoesNotExistError(Exception):
    """Raised when attempting to delete or update an actor that does not exist in the database."""


class SchemaAlreadyExistsError(Exception):
    """Raised when attempting to create a schema that already exists in the database."""


class SchemaDoesNotExistError(Exception):
    """Raised when attempting to delete or update a schema that does not exist in the database."""
