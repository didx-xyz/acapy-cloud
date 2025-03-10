from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException
from app.models.definitions import CredentialSchema
from app.services.definitions.schemas import get_schemas_as_tenant

schema_1_issuer_did = "abc123"
schema_id_1 = f"{schema_1_issuer_did}:schema1"
schema_id_2 = f"xyz456:schema2"
schema_name_1 = "Test Schema 1"
schema_name_2 = "Test Schema 2"
schema_version_1 = "1.0"
schema_version_2 = "2.0"

mock_schemas = [
    CredentialSchema(
        id=schema_id_1,
        name=schema_name_1,
        version=schema_version_1,
        attribute_names=["attr1"],
    ),
    CredentialSchema(
        id=schema_id_2,
        name=schema_name_2,
        version=schema_version_2,
        attribute_names=["attr2"],
    ),
]


@pytest.mark.anyio
async def test_get_schemas_as_tenant_all():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        result = await get_schemas_as_tenant(mock_aries_controller)

        assert len(result) == 2
        assert all(isinstance(schema, CredentialSchema) for schema in result)
        assert [schema.id for schema in result] == [schema_id_1, schema_id_2]


@pytest.mark.anyio
async def test_get_schemas_as_tenant_by_id():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    mock_schema = mock_schemas[0]
    with patch(
        "app.services.definitions.schemas.get_trust_registry_schema_by_id",
        return_value=mock_schema,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=[mock_schema]
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"

        result = await get_schemas_as_tenant(
            mock_aries_controller, schema_id=schema_id_1
        )

        assert len(result) == 1
        assert isinstance(result[0], CredentialSchema)
        assert result[0].id == schema_id_1


@pytest.mark.anyio
async def test_get_schemas_as_tenant_filter_issuer_did():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"

        result = await get_schemas_as_tenant(
            mock_aries_controller, schema_issuer_did=schema_1_issuer_did
        )

        assert len(result) == 1
        assert result[0].id == schema_id_1


@pytest.mark.anyio
async def test_get_schemas_as_tenant_filter_name():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"

        result = await get_schemas_as_tenant(
            mock_aries_controller, schema_name=schema_name_1
        )

        assert len(result) == 1
        assert result[0].name == schema_name_1


@pytest.mark.anyio
async def test_get_schemas_as_tenant_filter_version():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id", return_value=mock_schemas
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"

        result = await get_schemas_as_tenant(
            mock_aries_controller, schema_version=schema_version_2
        )

        assert len(result) == 1
        assert result[0].version == schema_version_2


@pytest.mark.anyio
async def test_get_schemas_as_tenant_anoncreds():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_schemas_by_id",
        return_value=mock_schemas,
    ), patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar-anoncreds"
        result = await get_schemas_as_tenant(mock_aries_controller)

        assert len(result) == 2
        assert all(isinstance(schema, CredentialSchema) for schema in result)
        assert [schema.id for schema in result] == [schema_id_1, schema_id_2]


@pytest.mark.anyio
async def test_get_schemas_as_tenant_unsupported_wallet_type():
    mock_aries_controller = AsyncMock(spec=AcaPyClient)

    with patch(
        "app.services.definitions.schemas.get_wallet_type"
    ) as mock_get_wallet_type, patch(
        "app.services.definitions.schemas.get_trust_registry_schemas",
        return_value=[],
    ):
        mock_get_wallet_type.return_value = "unsupported"

        with pytest.raises(CloudApiException) as exc_info:
            await get_schemas_as_tenant(mock_aries_controller)

        assert exc_info.value.status_code == 500
        assert "Wallet type not supported. Cannot get schemas." in str(exc_info.value)
