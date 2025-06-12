import json

import pytest

from app.util.string import random_string
from shared.constants import TRUST_REGISTRY_URL
from shared.util.rich_async_client import RichAsyncClient

# Apply the marker to all tests in this module. Tests must run sequentially in same xdist group.
pytestmark = pytest.mark.xdist_group(name="sequential_test_group")

new_actor = {
    "id": "darth-vader",
    "name": "Darth Vader",
    "roles": ["issuer", "verifier"],
    "didcomm_invitation": "string",
    "did": "did:key:string",
    "image_url": "https://example.com/image",
}
actor_id = new_actor["id"]
actor_did = new_actor["did"]
actor_name = new_actor["name"]


def generate_actor() -> dict[str, str]:
    return {
        "id": random_string(8),
        "name": random_string(8),
        "roles": ["issuer", "verifier"],
        "didcomm_invitation": random_string(8),
        "did": f"did:key:{random_string(5)}",
        "image_url": f"https://example.com/{random_string(8)}",
    }


@pytest.mark.anyio
async def test_get_actors() -> None:
    async with RichAsyncClient() as client:
        response = await client.get(f"{TRUST_REGISTRY_URL}/registry/actors")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_register_actor() -> None:
    payload = json.dumps(new_actor)
    name_payload = generate_actor()
    name_payload["name"] = new_actor["name"]
    name_payload = json.dumps(name_payload)

    did_payload = generate_actor()
    did_payload["did"] = new_actor["did"]
    did_payload = json.dumps(did_payload)

    didcomm_payload = generate_actor()
    didcomm_payload["didcomm_invitation"] = new_actor["didcomm_invitation"]
    didcomm_payload = json.dumps(didcomm_payload)

    id_payload = generate_actor()
    id_payload["id"] = new_actor["id"]
    id_payload = json.dumps(id_payload)

    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/actors",
            content=payload,
        )
        assert response.json() == json.loads(payload)
        assert response.status_code == 200

        new_actor_response = await client.get(f"{TRUST_REGISTRY_URL}/registry/actors")
        assert new_actor_response.status_code == 200
        new_actors = new_actor_response.json()
        assert new_actor["id"] in [actor["id"] for actor in new_actors]

        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/actors",
            content=name_payload,
        )
        assert response.status_code == 409
        assert "Bad request: An actor with name:" in response.json()["detail"]

        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/actors",
            content=did_payload,
        )
        assert response.status_code == 409
        assert "Bad request: An actor with DID:" in response.json()["detail"]

        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/actors",
            content=didcomm_payload,
        )
        assert response.status_code == 409
        assert "Bad request: An actor with DIDComm" in response.json()["detail"]

        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/actors",
            content=id_payload,
        )
        assert response.status_code == 409
        assert "Bad request: An actor with ID:" in response.json()["detail"]


@pytest.mark.anyio
async def test_get_actor() -> None:
    async with RichAsyncClient(raise_status_error=False) as client:
        # test by id
        response = await client.get(f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}")

        assert response.status_code == 200
        assert response.json() == new_actor

        not_actor_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/not_a_actor"
        )

        assert not_actor_response.status_code == 404

        # test by did
        response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/did/{actor_did}"
        )

        assert response.status_code == 200
        assert response.json() == new_actor

        not_actor_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/did/not_a_actor"
        )

        assert not_actor_response.status_code == 404

        # test by name
        response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/name/{actor_name}"
        )

        assert response.status_code == 200
        assert response.json() == new_actor

        not_actor_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/actors/name/not_a_actor"
        )

        assert not_actor_response.status_code == 404


@pytest.mark.anyio
async def test_update_actor() -> None:
    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.put(
            f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}",
            json=new_actor,
        )
        assert response.status_code == 200
        assert response.json() == new_actor

        new_actors_response = await client.get(f"{TRUST_REGISTRY_URL}/registry/actors")
        assert new_actors_response.status_code == 200
        new_actors_list = new_actors_response.json()
        assert new_actor in new_actors_list

        response = await client.put(
            f"{TRUST_REGISTRY_URL}/registry/actors/bad",
            json=new_actor,
        )
        assert response.status_code == 400


@pytest.mark.anyio
async def test_update_actor_x() -> None:
    updated_actor = new_actor.copy()
    updated_actor["did"] = None

    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.put(
            f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}",
            json=updated_actor,
        )

    assert response.status_code == 422
    response_detail = response.json()["detail"][0]
    assert response_detail["loc"] == ["body", "did"]
    assert response_detail["msg"] == "Input should be a valid string"
    assert response_detail["type"] == "string_type"


@pytest.mark.anyio
async def test_remove_actors() -> None:
    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.delete(
            f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}"
        )
        assert response.status_code == 204
        assert not response.text

        response = await client.delete(
            f"{TRUST_REGISTRY_URL}/registry/actors/{actor_id}"
        )
        assert response.status_code == 404
        assert "Actor with id" in response.json()["detail"]
