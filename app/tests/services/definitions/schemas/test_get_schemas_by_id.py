from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import AcaPyClient, ModelSchema, SchemaGetResult

from app.models.definitions import CredentialSchema
from app.services.definitions.schemas import get_schemas_by_id

schema_id_1 = "CXQseFxV34pcb8vf32XhEa:2:Test_Schema_1:1.0"
schema_id_2 = "CXQseFxV34pcb8vf32XhEa:2:Test_Schema_2:2.0"
schema_name_1 = "Test_Schema_1"
schema_name_2 = "Test_Schema_2"
schema_version_1 = "1.0"
schema_version_2 = "2.0"
attribute_names_1 = ["attr1"]
attribute_names_2 = ["attr2"]


@pytest.mark.anyio
async def test_get_schemas_by_id_success():
    mock_aries_controller = AsyncMock()
    mock_schema_ids = [schema_id_1, schema_id_2]
    mock_schema_results = [
        SchemaGetResult(
            var_schema=ModelSchema(
                id=schema_id_1,
                name=schema_name_1,
                version=schema_version_1,
                attr_names=attribute_names_1,
            )
        ),
        SchemaGetResult(
            var_schema=ModelSchema(
                id=schema_id_2,
                name=schema_name_2,
                version=schema_version_2,
                attr_names=attribute_names_2,
            )
        ),
    ]

    with patch(
        "app.services.definitions.schemas.handle_acapy_call",
        side_effect=mock_schema_results,
    ), patch(
        "app.services.definitions.schemas.credential_schema_from_acapy",
        side_effect=lambda x: CredentialSchema(
            id=x.id, name=x.name, version=x.version, attribute_names=x.attr_names
        ),
    ):

        result = await get_schemas_by_id(mock_aries_controller, mock_schema_ids, "askar")

        assert len(result) == 2
        assert all(isinstance(schema, CredentialSchema) for schema in result)
        assert [schema.id for schema in result] == mock_schema_ids
        assert [schema.name for schema in result] == [schema_name_1, schema_name_2]
        assert [schema.version for schema in result] == [
            schema_version_1,
            schema_version_2,
        ]
        assert [schema.attribute_names for schema in result] == [
            attribute_names_1,
            attribute_names_2,
        ]


@pytest.mark.anyio
async def test_get_schemas_by_id_empty_list():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    result = await get_schemas_by_id(mock_aries_controller, [], "askar")

    assert len(result) == 0


@pytest.mark.anyio
async def test_get_schemas_by_id_error_handling():
    mock_aries_controller = AsyncMock()

    mock_schema_ids = [schema_id_1, schema_id_2]

    with patch(
        "app.services.definitions.schemas.handle_acapy_call",
        side_effect=Exception("Test error"),
    ):
        with pytest.raises(Exception) as exc_info:
            await get_schemas_by_id(mock_aries_controller, mock_schema_ids, "askar")

        assert str(exc_info.value) == "Test error"
