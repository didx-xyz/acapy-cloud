import pytest

from shared.constants import TRUST_REGISTRY_URL
from shared.util.rich_async_client import RichAsyncClient
from trustregistry.registry.registry_schemas import SchemaID, _get_schema_attrs

# Apply the marker to all tests in this module. Tests must run sequentially in same xdist group.
pytestmark = pytest.mark.xdist_group(name="sequential_test_group")

schema_id = "string:2:string:string"
updated_schema_id = "string_updated:2:string_updated:string_updated"


@pytest.mark.anyio
async def test_get_schemas() -> None:
    async with RichAsyncClient() as client:
        response = await client.get(f"{TRUST_REGISTRY_URL}/registry/schemas")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_register_schema() -> None:
    schema_dict = {
        "id": schema_id,
        "did": "string",
        "name": "string",
        "version": "string",
    }
    payload = {"schema_id": schema_id}

    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/schemas",
            json=payload,
        )

        assert response.json() == schema_dict
        assert response.status_code == 200

        new_schemas_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}"
        )
        assert new_schemas_response.status_code == 200
        new_schema = new_schemas_response.json()
        assert schema_id == new_schema["id"]

        response = await client.post(
            f"{TRUST_REGISTRY_URL}/registry/schemas",
            json=payload,
        )
        assert response.status_code == 409
        assert "Schema already exists" in response.json()["detail"]


@pytest.mark.anyio
async def test_get_schema_by_id() -> None:
    schema_dict = {
        "id": schema_id,
        "did": "string",
        "name": "string",
        "version": "string",
    }

    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}"
        )
        assert response.json() == schema_dict
        assert response.status_code == 200

        response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/schemas/i:dont:exist"
        )
        assert response.status_code == 404
        assert "Schema with id " in response.json()["detail"]


@pytest.mark.anyio
async def test_update_schema() -> None:
    schema_dict = {
        "id": updated_schema_id,
        "did": "string_updated",
        "name": "string_updated",
        "version": "string_updated",
    }
    payload = {"schema_id": updated_schema_id}

    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.put(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{schema_id}",
            json=payload,
        )
        assert response.json() == schema_dict
        assert response.status_code == 200

        updated_schema_response = await client.get(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{updated_schema_id}"
        )
        assert updated_schema_response.status_code == 200
        updated_schema = updated_schema_response.json()
        assert updated_schema_id == updated_schema["id"]

        response = await client.put(
            f"{TRUST_REGISTRY_URL}/registry/schemas/i:dont:exist",
            json=payload,
        )
        assert response.status_code == 405
        assert "Schema not found" in response.json()["detail"]


@pytest.mark.anyio
async def test_remove_schema() -> None:
    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.delete(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{updated_schema_id}"
        )
        assert response.status_code == 204
        assert not response.text

        response = await client.delete(
            f"{TRUST_REGISTRY_URL}/registry/schemas/{updated_schema_id}"
        )
        assert response.status_code == 404
        assert "Schema not found" in response.json()["detail"]


def test__get_schema_attrs() -> None:
    res = _get_schema_attrs(schema_id=SchemaID(schema_id="abc:2:Peter Parker:0.4.20"))

    assert res == ["abc", "2", "Peter Parker", "0.4.20"]
