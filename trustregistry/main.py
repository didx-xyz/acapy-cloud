import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from shared.constants import PROJECT_VERSION
from shared.log_config import get_logger
from shared.util.set_event_loop_policy import set_event_loop_policy
from trustregistry import crud
from trustregistry.database import engine
from trustregistry.db import get_db
from trustregistry.registry import registry_actors, registry_schemas

set_event_loop_policy()

logger = get_logger(__name__)

OPENAPI_NAME = os.getenv("OPENAPI_NAME", "Trust Registry")
ROOT_PATH = os.getenv("ROOT_PATH", "")


def check_migrations(db_engine: Engine, alembic_cfg: Config) -> bool:
    # Check if alembic_version table exists
    with db_engine.connect() as connection:
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        has_alembic_version = "alembic_version" in table_names
        has_actors_table = "actors" in table_names

    script = ScriptDirectory.from_config(alembic_cfg)
    if not has_alembic_version and has_actors_table:
        logger.info(
            "Alembic version table not found. Stamping with initial revision..."
        )
        try:
            initial_revision = script.get_base()
            command.stamp(alembic_cfg, initial_revision)
            logger.info(
                "Database stamped with initial migration version: {}", initial_revision
            )
        except Exception:  # pylint: disable=W0718
            logger.exception("Error stamping database")
            raise

    elif not has_alembic_version:
        logger.info("Alembic version table not found.")
        return False

    # Get current revision
    with db_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()

    head_rev = script.get_current_head()

    return current_rev == head_rev


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    alembic_cfg = Config("alembic.ini")

    if not check_migrations(engine, alembic_cfg):
        logger.info("Applying database migrations...")
        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Database schema is up to date.")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error during migration")
            raise
    else:
        logger.info("Database is up to date. No migrations needed.")

    logger.debug("TrustRegistry startup: Validate tables are created")
    with engine.connect() as connection:
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        logger.debug("TrustRegistry tables created: `{}`", table_names)
    # start-up logic is before the yield
    yield
    # shutdown logic after


def create_app() -> FastAPI:
    application = FastAPI(
        root_path=ROOT_PATH,
        title=OPENAPI_NAME,
        version=PROJECT_VERSION,
        description="Welcome to the OpenAPI interface to the Aries CloudAPI trust registry",
        lifespan=lifespan,
        redoc_url=None,
        docs_url=None,
    )
    application.include_router(registry_actors.router)
    application.include_router(registry_schemas.router)
    return application


app = create_app()


# Use Scalar instead of Swagger
@app.get("/docs", include_in_schema=False)
async def scalar_html() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/")
async def root(db_session: Session = Depends(get_db)) -> dict[str, Any]:
    logger.debug("GET request received: Fetch actors and schemas from registry")
    db_schemas = crud.get_schemas(db_session)
    db_actors = crud.get_actors(db_session)
    schemas_repr = [schema.id for schema in db_schemas]
    logger.debug("Successfully fetched actors and schemas from registry.")
    return {"actors": db_actors, "schemas": schemas_repr}


@app.get("/registry")
async def registry(db_session: Session = Depends(get_db)) -> dict[str, Any]:
    return await root(db_session)
