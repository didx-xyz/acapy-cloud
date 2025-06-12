from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    AnonCredsSchema,
    SchemaPostOption,
    SchemaPostRequest,
)

from app.models.definitions import CreateSchema, CredentialSchema, SchemaType
from app.services.definitions.schemas import create_schema

sample_schema_id = "CXQseFxV34pcb8vf32XhEa:2:test_schema:0.3.0"
sample_schema_name = "test_schema"
sample_schema_version = "0.3.0"
sample_attribute_names = ["attr1", "attr2"]


@pytest.mark.anyio
async def test_create_schema_anoncreds_success():
    mock_aries_controller = AsyncMock()

    mock_schema_publisher = AsyncMock()
    mock_schema_publisher.publish_anoncreds_schema.return_value = CredentialSchema(
        id=sample_schema_id,
        name=sample_schema_name,
        version=sample_schema_version,
        attribute_names=sample_attribute_names,
    )

    create_schema_payload = CreateSchema(
        schema_type=SchemaType.ANONCREDS,
        name=sample_schema_name,
        version=sample_schema_version,
        attribute_names=sample_attribute_names,
    )

    with (
        patch(
            "app.services.definitions.schemas.GOVERNANCE_AGENT_URL",
            "https://governance-agent-url",
        ),
        patch(
            "app.services.definitions.schemas.SchemaPublisher",
            return_value=mock_schema_publisher,
        ),
        patch(
            "app.services.definitions.schemas.handle_model_with_validation"
        ) as mock_handle_model,
    ):
        mock_handle_model.side_effect = [
            AnonCredsSchema(
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=sample_attribute_names,
                issuer_id="test_did",
            ),
            SchemaPostRequest(
                var_schema=AnonCredsSchema(
                    name=sample_schema_name,
                    version=sample_schema_version,
                    attr_names=sample_attribute_names,
                    issuer_id="test_did",
                ),
                options=SchemaPostOption(),
            ),
        ]

        result = await create_schema(
            mock_aries_controller, create_schema_payload, public_did="test_did"
        )

        assert isinstance(result, CredentialSchema)
        assert result.id == sample_schema_id
        assert result.name == sample_schema_name
        assert result.version == sample_schema_version
        assert result.attribute_names == sample_attribute_names

        mock_schema_publisher.publish_anoncreds_schema.assert_called_once()
        assert mock_handle_model.call_count == 2
