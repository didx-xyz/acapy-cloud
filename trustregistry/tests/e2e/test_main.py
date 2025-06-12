import pytest

from shared.constants import TRUST_REGISTRY_URL
from shared.util.rich_async_client import RichAsyncClient
from trustregistry.main import create_app
from trustregistry.registry import registry_actors, registry_schemas


def test_create_app() -> None:
    app = create_app()
    assert app.title == "Trust Registry"

    # Verifying that all routes are included
    routes = [route.path for route in app.routes]
    expected_routes = [
        r.path for r in (registry_actors.router.routes + registry_schemas.router.routes)
    ]
    for route in expected_routes:
        assert route in routes


@pytest.mark.anyio
async def test_root() -> None:
    async with RichAsyncClient() as client:
        response = await client.get(TRUST_REGISTRY_URL)

    assert response.status_code == 200
    json_response = response.json()
    assert all(key in json_response for key in ["actors", "schemas"])


@pytest.mark.anyio
async def test_registry() -> None:
    async with RichAsyncClient() as client:
        response = await client.get(f"{TRUST_REGISTRY_URL}/registry")

    assert response.status_code == 200
    json_response = response.json()
    assert all(key in json_response for key in ["actors", "schemas"])
