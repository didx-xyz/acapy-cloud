from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.trustregistry import Actor, Schema
from trustregistry import crud, db
from trustregistry.crud import (
    ActorAlreadyExistsError,
    ActorDoesNotExistError,
    SchemaAlreadyExistsError,
    SchemaDoesNotExistError,
)

# pylint: disable=redefined-outer-name


@pytest.fixture
def db_session_mock() -> Mock:
    session = Mock(spec=AsyncSession)
    # Mock async methods
    session.scalars = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


db_actor1 = db.Actor(id="1", name="Alice", roles=["issuer"], did="did:123")
db_actor2 = db.Actor(id="2", name="Bob", roles=["issuer"], did="did:456")
actor1 = Actor(id="1", name="Alice", roles=["issuer"], did="did:123")
actor2 = Actor(id="2", name="Bob", roles=["issuer"], did="did:456")

db_schema1 = db.Schema(did="did:123", name="schema1", version="1.0")
db_schema2 = db.Schema(did="did:123", name="schema2", version="1.0")
schema1 = Schema(did="did123", name="schema1", version="1.0")


@pytest.mark.parametrize(
    "expected, skip, limit",
    [
        ([db_actor1, db_actor2], 0, 1000),
        ([], 0, 1000),
        ([db_actor1, db_actor2], 0, 2),
    ],
)
@pytest.mark.anyio
async def test_get_actors(db_session_mock: AsyncSession, expected, skip, limit):
    # Mock the result object that scalars returns
    mock_result = Mock()
    mock_result.all.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        actors = await crud.get_actors(db_session_mock, skip=skip, limit=limit)

        db_session_mock.scalars.assert_called_once()
        assert actors == expected

        select_mock.assert_called_once_with(db.Actor)
        select_mock(db.Actor).offset.assert_called_once_with(skip)
        select_mock(db.Actor).offset(skip).limit.assert_called_once_with(limit)


@pytest.mark.parametrize(
    "expected, actor_did",
    [(db_actor1, "did:123"), (None, "did:not_in_db")],
)
@pytest.mark.anyio
async def test_get_actor_by_did(db_session_mock: AsyncSession, expected, actor_did):
    mock_result = Mock()
    mock_result.first.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        if expected:
            actor = await crud.get_actor_by_did(db_session_mock, actor_did=actor_did)

            db_session_mock.scalars.assert_called_once()

            assert actor == expected
        else:
            with pytest.raises(ActorDoesNotExistError):
                await crud.get_actor_by_did(db_session_mock, actor_did=actor_did)

        select_mock.assert_called_once_with(db.Actor)
        select_mock(db.Actor).where.assert_called_once()


@pytest.mark.parametrize(
    "expected, actor_name", [(db_actor1, "Alice"), (None, "NotInDB")]
)
@pytest.mark.anyio
async def test_get_actor_by_name(db_session_mock: AsyncSession, expected, actor_name):
    mock_result = Mock()
    mock_result.one_or_none.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        if expected:
            result = await crud.get_actor_by_name(
                db_session_mock, actor_name=actor_name
            )

            db_session_mock.scalars.assert_called_once()
            assert result == expected
        else:
            with pytest.raises(ActorDoesNotExistError):
                await crud.get_actor_by_name(db_session_mock, actor_name=actor_name)

        select_mock.assert_called_once_with(db.Actor)
        select_mock(db.Actor).where.assert_called_once()


@pytest.mark.parametrize("expected, actor_id", [(db_actor1, "1"), (None, "NotInDB")])
@pytest.mark.anyio
async def test_get_actor_by_id(db_session_mock: AsyncSession, expected, actor_id):
    mock_result = Mock()
    mock_result.first.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        if expected:
            result = await crud.get_actor_by_id(db_session_mock, actor_id=actor_id)

            db_session_mock.scalars.assert_called_once()
            assert result == expected
        else:
            with pytest.raises(ActorDoesNotExistError):
                await crud.get_actor_by_id(db_session_mock, actor_id=actor_id)

        select_mock.assert_called_once_with(db.Actor)
        select_mock(db.Actor).where.assert_called_once()


@pytest.mark.anyio
async def test_create_actor(db_session_mock: AsyncSession):
    db_actor = db.Actor(**actor1.model_dump())

    result = await crud.create_actor(db_session_mock, actor1)

    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_called_once()
    db_session_mock.refresh.assert_called_once()

    assert result.did == db_actor.did
    assert result.name == db_actor.name
    assert result.roles == db_actor.roles


@pytest.mark.parametrize(
    "orig",
    [
        "actors_pkey",
        "ix_actors_name",
        "ix_actors_didcomm_invitation",
        "ix_actors_did",
        "unknown_orig",
    ],
)
@pytest.mark.anyio
async def test_create_actor_already_exists(db_session_mock: AsyncSession, orig: str):
    db_session_mock.add.side_effect = IntegrityError(
        orig=orig, params=None, statement=None
    )

    with pytest.raises(ActorAlreadyExistsError):
        await crud.create_actor(db_session_mock, actor1)


@pytest.mark.anyio
async def test_create_actor_exception(db_session_mock: AsyncSession):
    db_session_mock.add.side_effect = RuntimeError("Some error")

    with pytest.raises(RuntimeError):
        await crud.create_actor(db_session_mock, actor1)


@pytest.mark.parametrize("actor, actor_id", [(actor1, "1"), (None, "NotInDB")])
@pytest.mark.anyio
async def test_delete_actor(db_session_mock: AsyncSession, actor, actor_id):
    mock_result = Mock()
    mock_result.one_or_none.return_value = actor
    db_session_mock.scalars.return_value = mock_result

    with (
        patch("trustregistry.crud.select") as select_mock,
        patch("trustregistry.crud.delete") as delete_mock,
    ):
        if actor:
            result = await crud.delete_actor(db_session_mock, actor_id=actor_id)

            select_mock.assert_called_once_with(db.Actor)
            select_mock(db.Actor).where.assert_called_once()

            delete_mock.assert_called_once_with(db.Actor)
            delete_mock(db.Actor).where.assert_called_once()

            db_session_mock.execute.assert_called_once()
            db_session_mock.commit.assert_called_once()

            assert result == actor
        else:
            with pytest.raises(ActorDoesNotExistError):
                await crud.delete_actor(db_session_mock, actor_id=actor_id)


@pytest.mark.parametrize("new_actor, old_actor ", [(actor1, db_actor1), (actor1, None)])
@pytest.mark.anyio
async def test_update_actor(
    db_session_mock: AsyncSession, new_actor: Actor, old_actor: db.Actor
):
    mock_result = Mock()
    mock_result.one_or_none.return_value = old_actor
    db_session_mock.scalars.return_value = mock_result

    if not old_actor:
        with pytest.raises(ActorDoesNotExistError):
            await crud.update_actor(db_session_mock, new_actor)
    else:
        with patch("trustregistry.crud.update") as update_mock:
            # Mock the result for the update query
            mock_update_result = Mock()
            mock_update_result.first.return_value = old_actor
            # For update operations, we need to mock scalars twice
            db_session_mock.scalars.side_effect = [mock_result, mock_update_result]

            await crud.update_actor(db_session_mock, new_actor)

            update_mock.assert_called_once_with(db.Actor)
            update_mock(db.Actor).where.assert_called_once()
            update_mock(db.Actor).where().values.assert_called_once()

            db_session_mock.commit.assert_called_once()


@pytest.mark.parametrize(
    "expected, skip, limit",
    [
        ([db_schema1, db_schema2], 0, 1000),
        ([], 0, 1000),
        ([db_schema1, db_schema2], 0, 2),
    ],
)
@pytest.mark.anyio
async def test_get_schemas(db_session_mock: AsyncSession, expected, skip, limit):
    mock_result = Mock()
    mock_result.all.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        schemas = await crud.get_schemas(db_session_mock, skip=skip, limit=limit)

        db_session_mock.scalars.assert_called_once()
        assert schemas == expected

        select_mock.assert_called_once_with(db.Schema)
        select_mock(db.Schema).offset.assert_called_once_with(skip)
        select_mock(db.Schema).offset(skip).limit.assert_called_once_with(limit)


@pytest.mark.parametrize(
    "expected, schema_id", [(db_schema1, "123"), (None, "id_not_in_db")]
)
@pytest.mark.anyio
async def test_get_schema_by_id(db_session_mock: AsyncSession, expected, schema_id):
    mock_result = Mock()
    mock_result.first.return_value = expected
    db_session_mock.scalars.return_value = mock_result

    with patch("trustregistry.crud.select") as select_mock:
        if expected:
            schema = await crud.get_schema_by_id(db_session_mock, schema_id=schema_id)

            db_session_mock.scalars.assert_called_once()

            assert schema == expected
        else:
            with pytest.raises(SchemaDoesNotExistError):
                await crud.get_schema_by_id(db_session_mock, schema_id=schema_id)

        select_mock.assert_called_once_with(db.Schema)
        select_mock(db.Schema).where.assert_called_once()


@pytest.mark.parametrize("should_raise_integrity_error", [False, True])
@pytest.mark.anyio
async def test_create_schema(
    db_session_mock: AsyncSession, should_raise_integrity_error
):
    new_schema = schema1
    schema = db.Schema(**new_schema.model_dump())

    if should_raise_integrity_error:
        # Mock IntegrityError to test the exception handling
        db_session_mock.add.side_effect = IntegrityError(
            orig="duplicate key", params=None, statement=None
        )
        with pytest.raises(SchemaAlreadyExistsError):
            await crud.create_schema(db_session_mock, new_schema)
        db_session_mock.rollback.assert_called_once()
    else:
        # Test successful creation
        result = await crud.create_schema(db_session_mock, new_schema)
        db_session_mock.add.assert_called_once()
        db_session_mock.commit.assert_called_once()
        db_session_mock.refresh.assert_called_once()

        assert result.id == schema.id
        assert result.did == schema.did
        assert result.name == schema.name
        assert result.version == schema.version


@pytest.mark.parametrize(
    "new_schema, old_schema",
    [
        (
            Schema(
                did="did123",
                name="schema_new",
                version="1.0",
                id="did123:2:schema_new:1.0",
            ),
            db_schema1,
        ),
        (schema1, None),
    ],
)
@pytest.mark.anyio
async def test_update_schema(db_session_mock: AsyncSession, new_schema, old_schema):
    mock_result = Mock()
    mock_result.one_or_none.return_value = old_schema
    db_session_mock.scalars.return_value = mock_result

    if not old_schema:
        with pytest.raises(SchemaDoesNotExistError):
            await crud.update_schema(db_session_mock, new_schema, new_schema.id)
    else:
        with patch("trustregistry.crud.update") as update_mock:
            # Mock the result for the update query
            mock_update_result = Mock()
            mock_update_result.first.return_value = old_schema
            # For update operations, we need to mock scalars twice
            db_session_mock.scalars.side_effect = [mock_result, mock_update_result]

            await crud.update_schema(db_session_mock, new_schema, new_schema.id)

            update_mock.assert_called_once_with(db.Schema)
            update_mock(db.Schema).where.assert_called_once()
            update_mock(db.Schema).where().values.assert_called_once()

            db_session_mock.commit.assert_called_once()


@pytest.mark.parametrize(
    "schema, schema_id", [(db_schema1, "did123:2:schema1:1.0"), (None, "not_in_db")]
)
@pytest.mark.anyio
async def test_delete_schema(db_session_mock: AsyncSession, schema, schema_id):
    mock_result = Mock()
    mock_result.one_or_none.return_value = schema
    db_session_mock.scalars.return_value = mock_result

    with (
        patch("trustregistry.crud.select") as select_mock,
        patch("trustregistry.crud.delete") as delete_mock,
    ):
        if schema:
            result = await crud.delete_schema(db_session_mock, schema_id)

            select_mock.assert_called_once_with(db.Schema)
            select_mock(db.Schema).where.assert_called_once()

            delete_mock.assert_called_once_with(db.Schema)
            delete_mock(db.Schema).where.assert_called_once()

            db_session_mock.execute.assert_called_once()
            db_session_mock.commit.assert_called_once()

            assert result == schema
        else:
            with pytest.raises(SchemaDoesNotExistError):
                await crud.delete_schema(db_session_mock, schema_id)
