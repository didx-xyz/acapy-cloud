from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.trustregistry import Actor
from trustregistry.crud import ActorAlreadyExistsError, ActorDoesNotExistError
from trustregistry.registry import registry_actors


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


@pytest.mark.anyio
async def test_get_actors(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.get_actors") as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = [actor]
        result = await registry_actors.get_actors(db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock)
        assert result == [actor]


@pytest.mark.anyio
async def test_register_actor(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.create_actor") as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = actor
        result = await registry_actors.register_actor(actor, db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor=actor)
        assert result == actor


@pytest.mark.anyio
async def test_register_actor_already_exists(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.create_actor") as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.side_effect = ActorAlreadyExistsError("Actor already exists")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.register_actor(actor, db_session_mock)
        assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_update_actor(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.update_actor") as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = actor
        result = await registry_actors.update_actor("1", actor, db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor=actor)
        assert result == actor


@pytest.mark.anyio
async def test_update_actor_not_found(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.update_actor") as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.side_effect = ActorDoesNotExistError("Actor not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.update_actor("1", actor, db_session_mock)
        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_update_actor_id_mismatch(db_session_mock):
    actor = Actor(
        id="2",  # Different from URL param
        name="Alice",
        roles=["issuer"],
        did="did:123",
    )
    with pytest.raises(HTTPException) as exc_info:
        await registry_actors.update_actor("1", actor, db_session_mock)
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_get_actor_by_did(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_did"
    ) as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_did("did:123", db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor_did="did:123")
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_did_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_did"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError("Actor not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.get_actor_by_did("did:123", db_session_mock)
        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_get_actor_by_id(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_id"
    ) as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_id("1", db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor_id="1")
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_id_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_id"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError("Actor not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.get_actor_by_id("1", db_session_mock)
        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_get_actor_by_name(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_name"
    ) as mock_crud:
        actor = Actor(
            id="1",
            name="Alice",
            roles=["issuer"],
            did="did:123",
        )
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_name("Alice", db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor_name="Alice")
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_name_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_name"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError("Actor not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.get_actor_by_name("Alice", db_session_mock)
        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_delete_actor(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.delete_actor") as mock_crud:
        mock_crud.return_value = None
        result = await registry_actors.remove_actor("1", db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, actor_id="1")
        assert result is None


@pytest.mark.anyio
async def test_delete_actor_not_found(db_session_mock):
    with patch("trustregistry.registry.registry_actors.crud.delete_actor") as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError("Actor not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_actors.remove_actor("1", db_session_mock)
        assert exc_info.value.status_code == 404
