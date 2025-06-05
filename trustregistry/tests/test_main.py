from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session

from trustregistry import db
from trustregistry.main import app, check_migrations, lifespan, registry, root


@pytest.fixture
def db_session_mock():
    session = Mock(spec=Session)
    return session


def test_create_app():
    assert app.title == "Trust Registry"

    routes = [route.path for route in app.routes]

    expected_routes = ["/", "/registry", "/docs"]
    for route in expected_routes:
        assert route in routes


@pytest.mark.anyio
@patch("trustregistry.main.engine")
@patch("trustregistry.main.check_migrations")
@patch("trustregistry.main.Config")
@patch("trustregistry.main.command")
@patch("trustregistry.main.logger")
@patch("trustregistry.main.inspect")
async def test_lifespan_migrations_needed(
    mock_inspect,
    mock_logger,
    mock_command,
    mock_config,
    mock_check_migrations,
    mock_engine,
):
    mock_check_migrations.return_value = False
    mock_config.return_value = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["table1", "table2"]
    mock_inspect.return_value = mock_inspector

    async with lifespan(FastAPI()):
        pass

    mock_check_migrations.assert_called_once_with(mock_engine, mock_config.return_value)
    mock_command.upgrade.assert_called_once_with(mock_config.return_value, "head")
    mock_logger.info.assert_any_call("Applying database migrations...")
    mock_logger.info.assert_any_call("Database schema is up to date.")
    mock_inspect.assert_called_once_with(
        mock_engine.connect.return_value.__enter__.return_value
    )
    mock_inspector.get_table_names.assert_called_once()
    mock_logger.debug.assert_called_with(
        "TrustRegistry tables created: `{}`", ["table1", "table2"]
    )


@pytest.mark.anyio
@patch("trustregistry.main.engine")
@patch("trustregistry.main.check_migrations")
@patch("trustregistry.main.Config")
@patch("trustregistry.main.command")
@patch("trustregistry.main.logger")
@patch("trustregistry.main.inspect")
async def test_lifespan_migration_error(
    mock_inspect,
    mock_logger,
    mock_command,
    mock_config,
    mock_check_migrations,
    mock_engine,
):
    # Mock return values
    mock_check_migrations.return_value = False
    mock_config.return_value = MagicMock()
    mock_command.upgrade.side_effect = Exception("Migration error")
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["table1", "table2"]
    mock_inspect.return_value = mock_inspector

    # Test the lifespan context, expecting an Exception
    with pytest.raises(Exception, match="Migration error"):
        async with lifespan(FastAPI()):
            pass

    # Assertions
    mock_check_migrations.assert_called_once_with(mock_engine, mock_config.return_value)
    mock_command.upgrade.assert_called_once_with(mock_config.return_value, "head")
    mock_logger.info.assert_called_with("Applying database migrations...")
    mock_logger.exception.assert_called_once_with("Error during migration")


@pytest.mark.anyio
@patch("trustregistry.main.engine")
@patch("trustregistry.main.check_migrations")
@patch("trustregistry.main.Config")
@patch("trustregistry.main.command")
@patch("trustregistry.main.logger")
@patch("trustregistry.main.inspect")
async def test_lifespan_no_migrations_needed(
    mock_inspect,
    mock_logger,
    mock_command,
    mock_config,
    mock_check_migrations,
    mock_engine,
):
    mock_check_migrations.return_value = True
    mock_config.return_value = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["table1", "table2"]
    mock_inspect.return_value = mock_inspector

    async with lifespan(FastAPI()):
        pass

    mock_check_migrations.assert_called_once_with(mock_engine, mock_config.return_value)
    mock_command.upgrade.assert_not_called()
    mock_logger.info.assert_called_with("Database is up to date. No migrations needed.")
    mock_inspect.assert_called_once_with(
        mock_engine.connect.return_value.__enter__.return_value
    )
    mock_inspector.get_table_names.assert_called_once()
    mock_logger.debug.assert_called_with(
        "TrustRegistry tables created: `{}`", ["table1", "table2"]
    )


# Test 1: alembic_version missing, actors exists
# Test 2: both alembic_version and actors missing
# Test 3: alembic_version exists, revisions don't match
# Test 4: alembic_version exists, revisions match
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
    mock_engine = MagicMock()
    mock_alembic_cfg = MagicMock()

    mock_inspector = MagicMock()
    table_names = []
    if has_alembic_version:
        table_names.append("alembic_version")
    if has_actors_table:
        table_names.append("actors")

    mock_inspector.get_table_names.return_value = table_names
    mock_inspect.return_value = mock_inspector

    mock_script = MagicMock()
    mock_script.get_current_head.return_value = head_rev
    mock_script.get_base.return_value = "initial_schema"
    mock_script_directory.from_config.return_value = mock_script

    mock_context = MagicMock()
    mock_context.get_current_revision.return_value = current_rev
    mock_migration_context.configure.return_value = mock_context

    # Run the function
    result = check_migrations(mock_engine, mock_alembic_cfg)

    # Assert the result
    assert result == expected

    # Verify mock calls
    mock_inspect.assert_called()
    mock_inspector.get_table_names.assert_called_once()
    mock_script_directory.from_config.assert_called_once_with(mock_alembic_cfg)

    if not has_alembic_version:
        if has_actors_table:
            mock_script.get_base.assert_called_once()
            mock_command.stamp.assert_called_once_with(
                mock_alembic_cfg, "initial_schema"
            )
            mock_logger.info.assert_any_call(
                "Alembic version table not found. Stamping with initial revision..."
            )
            mock_logger.info.assert_any_call(
                "Database stamped with initial migration version: {}", "initial_schema"
            )
        else:
            mock_logger.info.assert_any_call("Alembic version table not found.")
    else:
        mock_migration_context.configure.assert_called()
        mock_context.get_current_revision.assert_called_once()
        mock_script.get_current_head.assert_called_once()


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


@pytest.mark.anyio
async def test_registry(db_session_mock):  # pylint: disable=redefined-outer-name
    with patch("trustregistry.main.root") as mock_root:
        mock_root.return_value = {"actors": "actors", "schemas": "schemas"}

        response = await registry(db_session_mock)

        assert response == {"actors": "actors", "schemas": "schemas"}

        mock_root.assert_called_once_with(db_session_mock)
