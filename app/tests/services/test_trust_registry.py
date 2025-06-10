from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from httpx import Response
from pytest_mock import MockerFixture

from app.exceptions import TrustRegistryException
from app.routes.trust_registry import (
    get_actors,
    get_issuers,
    get_schema_by_id,
    get_schemas,
    get_verifiers,
)
from app.services.trust_registry.actors import (
    fetch_actor_by_did,
    fetch_actors_with_role,
    register_actor,
    remove_actor_by_id,
    update_actor,
)
from app.services.trust_registry.schemas import register_schema, remove_schema_by_id
from app.services.trust_registry.util.actor import actor_has_role, assert_actor_name
from app.services.trust_registry.util.issuer import assert_valid_issuer
from app.services.trust_registry.util.schema import registry_has_schema
from shared.constants import TRUST_REGISTRY_URL
from shared.models.trustregistry import Actor

sample_did = "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6"


@pytest.mark.anyio
async def test_assert_valid_issuer(
    mocker: MockerFixture,
):
    service_path = "app.services.trust_registry"
    actors_path = f"{service_path}.actors"
    schema_path = f"{service_path}.util.schema"

    patch_client_actors = mocker.patch(f"{actors_path}.RichAsyncClient")
    patch_client_schema = mocker.patch(f"{schema_path}.RichAsyncClient")

    actor = Actor(id="actor-id", roles=["issuer"], did=sample_did, name="abc")
    schema_id = "a_schema_id"

    # Mock the actor_by_did and registry_has_schema calls
    mocked_client_get_did = Mock()
    response_actor_by_did = Response(200, json=actor.model_dump())
    mocked_client_get_did.get = AsyncMock(return_value=response_actor_by_did)
    patch_client_actors.return_value.__aenter__.return_value = mocked_client_get_did

    mocked_client_get_schema = Mock()
    response_schema = Response(
        status_code=200,
        json={"id": schema_id, "did": sample_did, "version": "1.0", "name": "name"},
    )
    mocked_client_get_schema.get = AsyncMock(return_value=response_schema)
    patch_client_schema.return_value.__aenter__.return_value = mocked_client_get_schema

    # Valid issuer and schema
    await assert_valid_issuer(did=sample_did, schema_id=schema_id)

    # Schema is not registered in registry
    not_found_response = HTTPException(status_code=404)
    mocked_client_get_schema.get = AsyncMock(side_effect=not_found_response)
    patch_client_schema.return_value.__aenter__.return_value = mocked_client_get_schema
    with pytest.raises(
        TrustRegistryException,
        match=f"Schema with id {schema_id} is not registered in trust registry.",
    ):
        await assert_valid_issuer(did=sample_did, schema_id=schema_id)

    # No actor with specified did
    mocked_client_get_did.get = AsyncMock(return_value=Response(404))
    with pytest.raises(TrustRegistryException):
        await assert_valid_issuer(did=sample_did, schema_id=schema_id)

    # Actor does not have required role 'issuer'
    actor_without_issuer_role = Actor(
        id="actor-id", roles=["verifier"], did=sample_did, name="abc"
    )
    response_actor_without_issuer_role = Response(
        200, json=actor_without_issuer_role.model_dump()
    )
    mocked_client_get_did.get = AsyncMock(
        return_value=response_actor_without_issuer_role
    )
    with pytest.raises(
        TrustRegistryException,
        match="Actor actor-id does not have required role 'issuer'.",
    ):
        await assert_valid_issuer(did=sample_did, schema_id=schema_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_actor_has_role(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor_id = "id"
    verifier = Actor(id=actor_id, name="abc", roles=["verifier"], did=sample_did)
    issuer = Actor(id=actor_id, name="abc", roles=["issuer"], did=sample_did)
    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=verifier.model_dump())
    )
    assert await actor_has_role(actor_id, "issuer") is False

    mock_async_client.get = AsyncMock(
        return_value=Response(428, json=verifier.model_dump())
    )
    with pytest.raises(TrustRegistryException):
        await actor_has_role(actor_id, "issuer")

    mock_async_client.get = AsyncMock(
        return_value=Response(428, json=issuer.model_dump())
    )
    with pytest.raises(TrustRegistryException):
        await actor_has_role(actor_id, "issuer")

    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=issuer.model_dump())
    )
    assert await actor_has_role(actor_id, "issuer") is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_actor_by_did(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor = Actor(
        id="governance",
        roles=["verifier"],
        name="test",
        did="did:test",
    )

    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=actor.model_dump())
    )
    fetched_actor = await fetch_actor_by_did("did:test")
    mock_async_client.get.assert_called_once_with(
        TRUST_REGISTRY_URL + "/registry/actors/did/did:test"
    )
    assert fetched_actor == actor

    mock_async_client.get = AsyncMock(
        return_value=Response(500, json=actor.model_dump())
    )
    with pytest.raises(TrustRegistryException):
        await fetch_actor_by_did("did:test")

    mock_async_client.get = AsyncMock(return_value=Response(404, json={}))
    fetched_actor = await fetch_actor_by_did("did:test")
    assert fetched_actor is None


def dump_json(input_list: list[Actor]):
    return [item.model_dump() for item in input_list]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_actor_with_role(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actors = [
        Actor(id="a", roles=["issuer"], name="test", did="did:test"),
        Actor(id="b", roles=["issuer"], name="test", did="did:test"),
    ]
    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=dump_json(actors))
    )
    assert await fetch_actors_with_role("issuer") == actors

    actors = [
        Actor(id="a", roles=["issuer"], name="test", did="did:test"),
        Actor(id="b", roles=["verifier"], name="test", did="did:test"),
    ]
    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=dump_json(actors))
    )
    assert await fetch_actors_with_role("issuer") == [actors[0]]

    actors = [
        Actor(id="a", roles=["verifier"], name="test", did="did:test"),
        Actor(id="b", roles=["verifier"], name="test", did="did:test"),
    ]
    mock_async_client.get = AsyncMock(
        return_value=Response(428, json=dump_json(actors))
    )
    with pytest.raises(TrustRegistryException):
        await fetch_actors_with_role("issuer")

    actors = [
        Actor(id="a", roles=["verifier"], name="test", did="did:test"),
        Actor(id="b", roles=["verifier"], name="test", did="did:test"),
    ]
    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=dump_json(actors))
    )
    assert await fetch_actors_with_role("issuer") == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.util.schema"], indirect=True
)
async def test_registry_has_schema(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    schema_id = "did:name:version"
    # mock has schema
    response = Response(
        status_code=200,
        json={"id": schema_id, "did": sample_did, "version": "1.0", "name": "name"},
    )
    mock_async_client.get = AsyncMock(return_value=response)
    assert await registry_has_schema(schema_id) is True

    schema_id = "did_3:name:version"
    # mock does not have schema
    not_found_response = HTTPException(
        status_code=404,
        detail="Something went wrong when fetching schema from trust registry.",
    )

    mock_async_client.get = AsyncMock(side_effect=not_found_response)
    assert await registry_has_schema(schema_id) is False

    # mock 500
    error_response = HTTPException(
        status_code=500,
        detail="Something went wrong when fetching schema from trust registry.",
    )

    mock_async_client.get = AsyncMock(side_effect=error_response)
    with pytest.raises(HTTPException):
        await registry_has_schema(schema_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.schemas"], indirect=True
)
async def test_register_schema(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    schema_id = "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
    mock_async_client.post = AsyncMock(return_value=Response(200))
    await register_schema(schema_id=schema_id)
    mock_async_client.post.assert_called_once_with(
        TRUST_REGISTRY_URL + "/registry/schemas",
        json={"schema_id": schema_id},
    )

    mock_async_client.post = AsyncMock(side_effect=HTTPException(500))
    with pytest.raises(TrustRegistryException):
        await register_schema(schema_id=schema_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_register_actor(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor = Actor(
        id="actor-id",
        name="actor-name",
        roles=["issuer", "verifier"],
        did="did:actor-did",
        didcomm_invitation="actor-didcomm-invitation",
    )
    mock_async_client.post = AsyncMock(return_value=Response(200))
    await register_actor(actor=actor)
    mock_async_client.post.assert_called_once_with(
        TRUST_REGISTRY_URL + "/registry/actors", json=actor.model_dump()
    )

    mock_async_client.post = AsyncMock(return_value=Response(500))
    with pytest.raises(TrustRegistryException):
        await register_actor(actor=actor)

    mock_async_client.post = AsyncMock(
        return_value=Response(422, json={"error": "some error"})
    )
    with pytest.raises(TrustRegistryException):
        await register_actor(actor=actor)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_remove_actor_by_id(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor_id = "actor_id"
    mock_async_client.delete = AsyncMock(return_value=Response(200))
    await remove_actor_by_id(actor_id=actor_id)
    mock_async_client.delete.assert_called_once_with(
        TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}"
    )

    mock_async_client.delete = AsyncMock(return_value=Response(500))
    with pytest.raises(TrustRegistryException):
        await remove_actor_by_id(actor_id="actor_id")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.schemas"], indirect=True
)
async def test_remove_schema_by_id(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    schema_id = "schema_id"
    mock_async_client.delete = AsyncMock(return_value=Response(200))
    await remove_schema_by_id(schema_id=schema_id)
    mock_async_client.delete.assert_called_once_with(
        TRUST_REGISTRY_URL + f"/registry/schemas/{schema_id}"
    )

    mock_async_client.delete = AsyncMock(
        side_effect=HTTPException(status_code=500, detail="The error")
    )
    with pytest.raises(
        TrustRegistryException, match="Error removing schema from trust registry"
    ):
        await remove_schema_by_id(schema_id="schema_id")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_update_actor(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor_id = "actor_id"
    actor = Actor(
        id=actor_id,
        name="actor-name",
        roles=["issuer", "verifier"],
        did=sample_did,
        didcomm_invitation="actor-didcomm-invitation",
    )

    mock_async_client.put = AsyncMock(
        return_value=Response(200, json=actor.model_dump())
    )
    await update_actor(actor=actor)
    mock_async_client.put.assert_called_once_with(
        TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}",
        json=actor.model_dump(),
    )

    mock_async_client.put = AsyncMock(return_value=Response(500))
    with pytest.raises(TrustRegistryException):
        await update_actor(actor=actor)

    mock_async_client.put = AsyncMock(
        return_value=Response(422, json={"error": "some error"})
    )
    with pytest.raises(TrustRegistryException):
        await update_actor(actor=actor)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.util.actor"], indirect=True
)
async def test_assert_actor_name(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    # test actor exists
    name = "Numuhukumakiaki'aialunamor"
    actor = Actor(
        id="some_id",
        name=name,
        roles=["issuer", "verifier"],
        did=sample_did,
        didcomm_invitation="actor-didcomm-invitation",
    )
    mock_async_client.get = AsyncMock(
        return_value=Response(status_code=200, json=actor.model_dump())
    )

    assert await assert_actor_name(name) is True

    # test actor does not exists
    mock_async_client.get = AsyncMock(return_value=Response(status_code=404))

    assert await assert_actor_name("not_an_actor") is False

    # test exception (500)
    mock_async_client.get = AsyncMock(return_value=Response(500))
    with pytest.raises(TrustRegistryException):
        await assert_actor_name(name)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.schemas"], indirect=True
)
async def test_get_schemas(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    schemas = [
        {
            "did": "CW2GEk5zZ7DcF818i3gLUs",
            "name": "test_schema",
            "version": "9.46.70",
            "id": "CW2GEk5zZ7DcF818i3gLUs:2:test_schema:9.46.70",
        },
        {
            "did": "CW2GEk5zZ7DcF818i3gLUs",
            "name": "test_schema_alt",
            "version": "74.84.49",
            "id": "CW2GEk5zZ7DcF818i3gLUs:2:test_schema_alt:74.84.49",
        },
        {
            "did": "CW2GEk5zZ7DcF818i3gLUs",
            "name": "test_schema",
            "version": "35.12.23",
            "id": "CW2GEk5zZ7DcF818i3gLUs:2:test_schema:35.12.23",
        },
    ]

    mock_async_client.get = AsyncMock(return_value=Response(200, json=schemas))

    await get_schemas()

    mock_async_client.get.assert_called_once_with(
        f"{TRUST_REGISTRY_URL}/registry/schemas"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.schemas"], indirect=True
)
async def test_get_schema_by_id(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    schema = {
        "did": "CW2GEk5zZ7DcF818i3gLUs",
        "name": "test_schema",
        "version": "9.46.70",
        "id": "CW2GEk5zZ7DcF818i3gLUs:2:test_schema:9.46.70",
    }
    schema_id = schema["id"]
    mock_async_client.get = AsyncMock(return_value=Response(200, json=schema))

    await get_schema_by_id(schema_id)

    mock_async_client.get.assert_called_once_with(
        f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}"
    )

    mock_async_client.get = AsyncMock(
        return_value=Response(404, json={"error": "Schema not found"})
    )
    with pytest.raises(HTTPException):
        await get_schema_by_id(schema_id="bad_id")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_get_actor(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actor_id = "418bec12-7252-4edf-8bef-ee8dd661f934"
    actor_name = "faber_GWNKQ"

    actor = Actor(
        id=actor_id,
        name=actor_name,
        roles=["issuer"],
        did=sample_did,
        didcomm_invitation="https://governance-multitenant-agent:3020?oob=eyJAdHlwZ",
    ).model_dump()

    mock_async_client.get = AsyncMock(return_value=Response(200, json=[actor]))

    await get_actors()
    mock_async_client.get.assert_called_with(f"{TRUST_REGISTRY_URL}/registry/actors")

    # Following methods get 1 actor
    mock_async_client.get = AsyncMock(return_value=Response(200, json=actor))

    await get_actors(actor_did=sample_did)
    mock_async_client.get.assert_called_with(
        f"{TRUST_REGISTRY_URL}/registry/actors/did/{sample_did}"
    )

    await get_actors(actor_name=actor_name)
    mock_async_client.get.assert_called_with(
        f"{TRUST_REGISTRY_URL}/registry/actors/name/{actor_name}"
    )

    await get_actors(actor_id=actor_id)
    mock_async_client.get.assert_called_with(
        f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}"
    )

    mock_async_client.get = AsyncMock(
        return_value=Response(
            400, json={"error": "Bad request: More than one query parameter given"}
        )
    )
    with pytest.raises(HTTPException):
        await get_actors(actor_id=actor_id, actor_did=sample_did)

    mock_async_client.get = AsyncMock(
        return_value=Response(404, json={"error": "Actor not found"})
    )
    with pytest.raises(HTTPException):
        await get_actors(actor_id="bad_id")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_get_issuers(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actors = [
        Actor(
            id="418bec12-7252-4edf-8bef-ee8dd661f934",
            name="faber_GWNKQ",
            roles=["issuer"],
            did=sample_did,
            didcomm_invitation="https://governance-multitenant-agent:3020?oob=eyJAdHlwZ",
        ).model_dump()
    ]

    mock_async_client.get = AsyncMock(return_value=Response(200, json=actors))
    await get_issuers()

    mock_async_client.get.assert_called_once_with(
        f"{TRUST_REGISTRY_URL}/registry/actors"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_get_verifiers(
    mock_async_client: Mock,  # pylint: disable=redefined-outer-name
):
    actors = [
        Actor(
            id="418bec12-7252-4edf-8bef-ee8dd661f934",
            name="faber_GWNKQ",
            roles=["verifier"],
            did=sample_did,
            didcomm_invitation="https://governance-multitenant-agent:3020?oob=eyJAdHlwZ",
        ).model_dump()
    ]

    mock_async_client.get = AsyncMock(return_value=Response(200, json=actors))

    await get_verifiers()
    mock_async_client.get.assert_called_once_with(
        f"{TRUST_REGISTRY_URL}/registry/actors"
    )
