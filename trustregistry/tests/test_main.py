from unittest.mock import AsyncMock, Mock, patch

import pytest
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from trustregistry import db
from trustregistry.main import check_migrations, create_app, lifespan, root


@pytest.fixture
def db_session_mock():
    session = Mock(spec=AsyncSession)
    # Mock async methods
    session.scalars = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def engine_mock():
    return Mock(spec=Engine)


@pytest.fixture
def alembic_cfg_mock():
    return Mock(spec=Config)


def test_create_app():
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Trust Registry"


@pytest.mark.parametrize(
    "has_alembic_version,has_actors_table,current_rev,head_rev,expected",
    [
        (False, True, None, "head_rev", False),
        (False, False, None, "head_rev", False),
        (True, True, "current_rev", "head_rev", False),
        (True, True, "same_rev", "same_rev", True),
    ],
)
@patch("trustregistry.main.inspect")
@patch("trustregistry.main.MigrationContext")
@patch("trustregistry.main.ScriptDirectory")
@patch("trustregistry.main.command")
@patch("trustregistry.main.logger")
def test_check_migrations(
    mock_logger,
    mock_command,
    mock_script_directory,
    mock_migration_context,
    mock_inspect,
    has_alembic_version,
    has_actors_table,
    current_rev,
    head_rev,
    expected,
):
    # Set up mocks
    mock_connection = Mock()
    mock_engine = Mock()

    # Properly mock the context manager for engine.connect()
    mock_connection_context = Mock()
    mock_connection_context.__enter__ = Mock(return_value=mock_connection)
    mock_connection_context.__exit__ = Mock(return_value=None)
    mock_engine.connect.return_value = mock_connection_context

    mock_inspector = Mock()
    mock_inspect.return_value = mock_inspector

    table_names = []
    if has_alembic_version:
        table_names.append("alembic_version")
    if has_actors_table:
        table_names.append("actors")

    mock_inspector.get_table_names.return_value = table_names

    mock_context = Mock()
    mock_migration_context.configure.return_value = mock_context
    mock_context.get_current_revision.return_value = current_rev

    mock_script = Mock()
    mock_script_directory.from_config.return_value = mock_script
    mock_script.get_current_head.return_value = head_rev
    mock_script.get_base.return_value = "base_rev"

    mock_alembic_cfg = Mock()

    # Test
    result = check_migrations(mock_engine, mock_alembic_cfg)

    # Assertions
    assert result == expected

    if not has_alembic_version and has_actors_table:
        mock_command.stamp.assert_called_once_with(mock_alembic_cfg, "base_rev")
        mock_logger.info.assert_any_call(
            "Alembic version table not found. Stamping with initial revision..."
        )


@pytest.mark.anyio
async def test_lifespan_no_migrations_needed():
    with (
        patch("trustregistry.main.check_migrations") as mock_check_migrations,
        patch("trustregistry.main.engine") as mock_engine,
        patch("trustregistry.main.async_engine") as mock_async_engine,
        patch("trustregistry.main.inspect") as mock_inspect,
        patch("trustregistry.main.Config"),
    ):
        mock_check_migrations.return_value = True
        mock_connection = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_inspector = Mock()
        mock_inspect.return_value = mock_inspector
        mock_inspector.get_table_names.return_value = ["actors", "schemas"]
        mock_async_engine.dispose = AsyncMock()

        app_mock = Mock(spec=FastAPI)

        async with lifespan(app_mock):
            pass

        mock_check_migrations.assert_called_once()
        mock_async_engine.dispose.assert_called_once()


@pytest.mark.anyio
async def test_lifespan_migrations_needed():
    with (
        patch("trustregistry.main.check_migrations") as mock_check_migrations,
        patch("trustregistry.main.command") as mock_command,
        patch("trustregistry.main.engine") as mock_engine,
        patch("trustregistry.main.async_engine") as mock_async_engine,
        patch("trustregistry.main.inspect") as mock_inspect,
        patch("trustregistry.main.Config"),
    ):
        mock_check_migrations.return_value = False
        mock_connection = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_inspector = Mock()
        mock_inspect.return_value = mock_inspector
        mock_inspector.get_table_names.return_value = ["actors", "schemas"]
        mock_async_engine.dispose = AsyncMock()

        app_mock = Mock(spec=FastAPI)

        async with lifespan(app_mock):
            pass

        mock_check_migrations.assert_called_once()
        mock_command.upgrade.assert_called_once()
        mock_async_engine.dispose.assert_called_once()


@pytest.mark.anyio
async def test_root(db_session_mock):  # pylint: disable=redefined-outer-name
    schemas = [
        db.Schema(id="123", did="did:123", name="schema1", version="1.0"),
        db.Schema(id="456", did="did:123", name="schema2", version="1.0"),
    ]
    actors = [db.Actor(id="1", name="Alice"), db.Actor(id="2", name="Bob")]
    with (
        patch("trustregistry.main.crud.get_schemas") as mock_get_schemas,
        patch("trustregistry.main.crud.get_actors") as mock_get_actors,
    ):
        mock_get_schemas.return_value = schemas
        mock_get_actors.return_value = actors

        response = await root(db_session_mock)

        assert response == {"actors": actors, "schemas": ["123", "456"]}

        mock_get_schemas.assert_called_once_with(db_session_mock)
        mock_get_actors.assert_called_once_with(db_session_mock)
