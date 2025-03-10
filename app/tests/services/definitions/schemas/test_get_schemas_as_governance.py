from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import AdminConfig

from app.exceptions import CloudApiException
from app.models.definitions import CredentialSchema
from app.services.definitions.schemas import get_schemas_as_governance


@pytest.mark.anyio
async def test_get_schemas_as_governance_success():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://governance-agent-url"
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "askar"})
    )
    mock_schema_ids = ["schema1", "schema2"]
    mock_schemas = [
        CredentialSchema(
            id="schema1", name="Test Schema 1", version="1.0", attribute_names=["attr1"]
        ),
        CredentialSchema(
            id="schema2", name="Test Schema 2", version="2.0", attribute_names=["attr2"]
        ),
    ]

    mock_response = MagicMock()
    mock_response.schema_ids = mock_schema_ids

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ), patch(
        "app.services.definitions.schemas.handle_acapy_call", return_value=mock_response
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ):

        result = await get_schemas_as_governance(mock_aries_controller)

        assert len(result) == 2
        assert all(isinstance(schema, CredentialSchema) for schema in result)
        assert [schema.id for schema in result] == mock_schema_ids


@pytest.mark.anyio
async def test_get_schemas_as_governance_non_governance_agent():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://non-governance-agent-url"

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await get_schemas_as_governance(mock_aries_controller)

        assert exc_info.value.status_code == 403
        assert "Only governance agents are allowed to access this endpoint." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_get_schemas_as_governance_with_filters():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://governance-agent-url"
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "askar"})
    )
    mock_schema_ids = ["schema1"]
    mock_schemas = [
        CredentialSchema(
            id="schema1", name="Test Schema 1", version="1.0", attribute_names=["attr1"]
        ),
    ]

    mock_response = MagicMock()
    mock_response.schema_ids = mock_schema_ids

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ), patch(
        "app.services.definitions.schemas.handle_acapy_call", return_value=mock_response
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ):

        result = await get_schemas_as_governance(
            mock_aries_controller,
            schema_id="schema1",
            schema_issuer_did="did:sov:123",
            schema_name="Test Schema 1",
            schema_version="1.0",
        )

        assert len(result) == 1
        assert result[0].id == "schema1"
        assert result[0].name == "Test Schema 1"
        assert result[0].version == "1.0"


@pytest.mark.anyio
async def test_get_schemas_as_governance_no_schemas():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://governance-agent-url"
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "askar"})
    )
    mock_response = MagicMock()
    mock_response.schema_ids = None

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ), patch(
        "app.services.definitions.schemas.handle_acapy_call", return_value=mock_response
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=[]
    ):

        result = await get_schemas_as_governance(mock_aries_controller)

        assert len(result) == 0


@pytest.mark.anyio
async def test_get_schemas_as_governance_anoncreds():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://governance-agent-url"
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "askar-anoncreds"})
    )
    mock_schema_ids = ["schema1", "schema2"]
    mock_schemas = [
        CredentialSchema(
            id="schema1", name="Test Schema 1", version="1.0", attribute_names=["attr1"]
        ),
        CredentialSchema(
            id="schema2", name="Test Schema 2", version="2.0", attribute_names=["attr2"]
        ),
    ]

    mock_response = MagicMock()
    mock_response.schema_ids = mock_schema_ids

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ), patch(
        "app.services.definitions.schemas.handle_acapy_call", return_value=mock_response
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ):

        result = await get_schemas_as_governance(mock_aries_controller)

        assert len(result) == 2
        assert all(isinstance(schema, CredentialSchema) for schema in result)
        assert [schema.id for schema in result] == mock_schema_ids


@pytest.mark.anyio
async def test_get_schemas_as_governance_unsupported_wallet_type():
    mock_aries_controller = AsyncMock()
    mock_aries_controller.configuration.host = "https://governance-agent-url"
    mock_aries_controller.server.get_config = AsyncMock(
        return_value=AdminConfig(config={"wallet.type": "unsupported"})
    )

    with patch(
        "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
        "https://governance-agent-url",
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await get_schemas_as_governance(mock_aries_controller)

        assert exc_info.value.status_code == 500
        assert "Wallet type not supported. Cannot get schemas." in str(exc_info.value)
