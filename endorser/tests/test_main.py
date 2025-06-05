import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from endorser.main import app, app_lifespan, health_check, health_ready
from endorser.services.endorsement_processor import EndorsementProcessor
from endorser.services.endorser_config import EndorserConfig


def test_create_app():
    assert app.title == "Aries Cloud API: Endorser Service"

    # Verifying that all routes are included

    # Get all routes in app
    routes = [route.path for route in app.routes]

    expected_routes = ["/health/live", "/health/ready", "/docs"]
    for route in expected_routes:
        assert route in routes


@pytest.mark.anyio
async def test_app_lifespan():
    # Mocks for services and container
    endorsement_processor_mock = MagicMock(start=Mock(), stop=AsyncMock())
    container_mock = AsyncMock(
        endorsement_processor=AsyncMock(return_value=endorsement_processor_mock),
        wire=MagicMock(),
        shutdown_resources=AsyncMock(),
    )

    # Patch the Container to return the mocked container
    with (
        patch("endorser.main.Container", return_value=container_mock),
        patch.object(EndorserConfig, "initialize", new_callable=AsyncMock),
    ):
        # Run the app_lifespan context manager
        async with app_lifespan(FastAPI()):
            pass

        # Assert the container was wired with the correct modules
        container_mock.wire.assert_called_once()

        # Assert the endorsement_processor's start method was called
        endorsement_processor_mock.start.assert_called_once()

        # Assert the shutdown logic was called correctly
        endorsement_processor_mock.stop.assert_awaited_once()
        container_mock.shutdown_resources.assert_awaited_once()


@pytest.mark.anyio
async def test_health_check_healthy():
    endorsement_processor_mock = MagicMock(start=Mock(), stop=AsyncMock())
    endorsement_processor_mock.are_tasks_running.return_value = True

    response = await health_check(endorsement_processor=endorsement_processor_mock)
    assert response == {"status": "healthy"}


@pytest.mark.anyio
async def test_health_check_unhealthy():
    endorsement_processor_mock = MagicMock(start=Mock(), stop=AsyncMock())
    endorsement_processor_mock.are_tasks_running.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        await health_check(endorsement_processor=endorsement_processor_mock)
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "One or more background tasks are not running."


@pytest.mark.anyio
async def test_health_ready_success():
    endorsement_processor_mock = AsyncMock(spec=EndorsementProcessor)

    endorsement_processor_mock.check_jetstream.return_value = {
        "is_working": True,
        "streams_count": 1,
        "consumers_count": 1,
    }

    response = await health_ready(endorsement_processor=endorsement_processor_mock)

    assert response == {
        "status": "ready",
        "jetstream": {"is_working": True, "streams_count": 1, "consumers_count": 1},
    }


@pytest.mark.anyio
async def test_health_ready_jetstream_not_working():
    endorsement_processor_mock = AsyncMock(spec=EndorsementProcessor)

    endorsement_processor_mock.check_jetstream.return_value = {
        "is_working": False,
        "error": "No streams available",
    }

    with pytest.raises(HTTPException) as exc_info:
        await health_ready(endorsement_processor=endorsement_processor_mock)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "status": "not ready",
        "jetstream": "JetStream not ready",
    }


@pytest.mark.anyio
async def test_health_ready_timeout():
    endorsement_processor_mock = AsyncMock(spec=EndorsementProcessor)

    endorsement_processor_mock.check_jetstream.side_effect = asyncio.TimeoutError()

    with pytest.raises(HTTPException) as exc_info:
        await health_ready(endorsement_processor=endorsement_processor_mock)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "status": "not ready",
        "error": "JetStream health check timed out",
    }


@pytest.mark.anyio
async def test_health_ready_unexpected_error():
    endorsement_processor_mock = AsyncMock(spec=EndorsementProcessor)

    endorsement_processor_mock.check_jetstream.side_effect = Exception(
        "Unexpected error"
    )

    with pytest.raises(HTTPException) as exc_info:
        await health_ready(endorsement_processor=endorsement_processor_mock)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {"status": "error", "error": "Unexpected error"}


@pytest.mark.anyio
async def test_health_ready_with_timeout():
    endorsement_processor_mock = AsyncMock(spec=EndorsementProcessor)

    endorsement_processor_mock.check_jetstream.side_effect = (
        asyncio.TimeoutError
    )  # Simulate a slow response

    with pytest.raises(HTTPException) as exc_info:
        await health_ready(endorsement_processor=endorsement_processor_mock)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "status": "not ready",
        "error": "JetStream health check timed out",
    }


def test_scalar_html():
    client = TestClient(app)
    # Simulate a request to the /docs endpoint
    response = client.get("/docs")
    assert response.status_code == 200
