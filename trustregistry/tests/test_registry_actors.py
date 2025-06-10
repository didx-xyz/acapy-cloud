from unittest.mock import patch

import pytest
from fastapi.exceptions import HTTPException

from shared.models.trustregistry import Actor
from trustregistry.crud import ActorAlreadyExistsError, ActorDoesNotExistError
from trustregistry.registry import registry_actors


@pytest.mark.anyio
async def test_get_actors():
    with patch("trustregistry.registry.registry_actors.crud.get_actors") as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.return_value = [actor]
        result = await registry_actors.get_actors()
        mock_crud.assert_called_once()
        assert result == [actor]


@pytest.mark.anyio
async def test_register_actor():
    with patch("trustregistry.registry.registry_actors.crud.create_actor") as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.return_value = actor
        result = await registry_actors.register_actor(actor)
        mock_crud.assert_called_once()
        assert result == actor


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception, status_code", [(ActorAlreadyExistsError, 409), (Exception, 500)]
)
async def test_register_actor_x(exception, status_code):
    with patch("trustregistry.registry.registry_actors.crud.create_actor") as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["verifier"], did="did:sov:1234")
        mock_crud.side_effect = exception()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.register_actor(actor)

        mock_crud.assert_called_once()
        assert ex.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "actor_id, actor",
    [
        ("1", Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")),
        ("1", Actor(id="", name="Alice", roles=["issuer"], did="did:sov:1234")),
        ("2", Actor(id="1", name="Bob", roles=["verifier"], did="did:sov:5678")),
    ],
)
async def test_update_actor(actor_id: str, actor: Actor):
    with patch("trustregistry.registry.registry_actors.crud.update_actor") as mock_crud:
        mock_crud.return_value = actor

        if actor.id and actor_id != actor.id:
            with pytest.raises(HTTPException) as ex:
                await registry_actors.update_actor(actor_id, actor)

            mock_crud.assert_not_called()
            assert ex.value.status_code == 400

        else:
            result = await registry_actors.update_actor(actor_id, actor)
            mock_crud.assert_called_once()
            assert result == actor


@pytest.mark.anyio
async def test_update_actor_x():
    with patch("trustregistry.registry.registry_actors.crud.update_actor") as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.side_effect = ActorDoesNotExistError()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.update_actor("1", actor)

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404


@pytest.mark.anyio
async def test_get_actor_by_did():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_did"
    ) as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_did("did:sov:1234")
        mock_crud.assert_called_once()
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_did_x():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_did"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.get_actor_by_did("did:sov:1234")

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404


@pytest.mark.anyio
async def test_get_actor_by_id():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_id"
    ) as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_id("1")
        mock_crud.assert_called_once()
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_id_x():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_id"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.get_actor_by_id("1")

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404


@pytest.mark.anyio
async def test_get_actor_by_name():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_name"
    ) as mock_crud:
        actor = Actor(id="1", name="Alice", roles=["issuer"], did="did:sov:1234")
        mock_crud.return_value = actor
        result = await registry_actors.get_actor_by_name("Alice")
        mock_crud.assert_called_once()
        assert result == actor


@pytest.mark.anyio
async def test_get_actor_by_name_x():
    with patch(
        "trustregistry.registry.registry_actors.crud.get_actor_by_name"
    ) as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.get_actor_by_name("Alice")

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404


@pytest.mark.anyio
async def test_delete_actor():
    with patch("trustregistry.registry.registry_actors.crud.delete_actor") as mock_crud:
        mock_crud.return_value = None
        result = await registry_actors.remove_actor("1")
        mock_crud.assert_called_once()
        assert result is None


@pytest.mark.anyio
async def test_delete_actor_x():
    with patch("trustregistry.registry.registry_actors.crud.delete_actor") as mock_crud:
        mock_crud.side_effect = ActorDoesNotExistError()
        with pytest.raises(HTTPException) as ex:
            await registry_actors.remove_actor("1")

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404
