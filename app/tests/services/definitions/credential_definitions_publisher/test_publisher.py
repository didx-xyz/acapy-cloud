import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import CloudApiException
from app.services.definitions.credential_definition_publisher import (
    CredentialDefinitionPublisher,
)

# pylint: disable=redefined-outer-name
# because re-using fixtures in same module


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_controller():
    return AsyncMock()


@pytest.fixture
def publisher(mock_controller, mock_logger):
    return CredentialDefinitionPublisher(mock_controller, mock_logger)


@pytest.mark.anyio
async def test_check_endorser_connection_success(publisher):
    with patch(
        "app.services.definitions.credential_definition_publisher.check_endorser_connection",
        return_value=True,
    ):
        await publisher.check_endorser_connection()
        # If no exception is raised, the test passes


@pytest.mark.anyio
async def test_check_endorser_connection_failure(publisher):
    with patch(
        "app.services.definitions.credential_definition_publisher.check_endorser_connection",
        return_value=False,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.check_endorser_connection()
        assert "Credential definition creation failed" in str(exc_info.value)


@pytest.mark.anyio
async def test_publish_credential_definition_success(publisher):
    mock_request_body = MagicMock()
    mock_result = MagicMock()

    with patch(
        "app.services.definitions.credential_definition_publisher.handle_acapy_call",
        return_value=mock_result,
    ):
        result = await publisher.publish_credential_definition(mock_request_body)
        assert result == mock_result


@pytest.mark.anyio
async def test_publish_credential_definition_already_exists(publisher):
    mock_request_body = MagicMock()

    with patch(
        "app.services.definitions.credential_definition_publisher.handle_acapy_call",
        side_effect=CloudApiException(detail="already exists", status_code=400),
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_credential_definition(mock_request_body)
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail


@pytest.mark.anyio
async def test_publish_credential_definition_other_error(publisher):
    mock_request_body = MagicMock()

    with patch(
        "app.services.definitions.credential_definition_publisher.handle_acapy_call",
        side_effect=CloudApiException(detail="Some error", status_code=500),
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_credential_definition(mock_request_body)
        assert exc_info.value.status_code == 500
        assert "Error while creating credential definition" in exc_info.value.detail


@pytest.mark.anyio
async def test_wait_for_revocation_registry_success(publisher):
    mock_cred_def_id = "test_cred_def_id"

    with patch(
        "app.services.definitions.credential_definition_publisher.wait_for_active_registry"
    ), patch(
        "app.services.definitions.credential_definition_publisher.REGISTRY_CREATION_TIMEOUT",
        1,
    ):
        await publisher.wait_for_revocation_registry(mock_cred_def_id, "askar")
        # If no exception is raised, the test passes


@pytest.mark.anyio
async def test_wait_for_revocation_registry_timeout(publisher):
    mock_cred_def_id = "test_cred_def_id"

    with patch(
        "app.services.definitions.credential_definition_publisher.wait_for_active_registry",
        side_effect=asyncio.TimeoutError,
    ), patch(
        "app.services.definitions.credential_definition_publisher.REGISTRY_CREATION_TIMEOUT",
        0.1,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.wait_for_revocation_registry(mock_cred_def_id, "askar")
        assert exc_info.value.status_code == 504
        assert "Timeout waiting for revocation registry creation" in str(exc_info.value)
