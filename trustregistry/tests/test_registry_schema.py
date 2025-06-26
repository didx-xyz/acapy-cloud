from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.trustregistry import Schema
from trustregistry.crud import SchemaAlreadyExistsError, SchemaDoesNotExistError
from trustregistry.registry import registry_schemas


@pytest.fixture
def db_session_mock():
    session = Mock(spec=AsyncSession)
    # Mock async methods
    session.scalars = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.anyio
async def test_get_schemas(db_session_mock):
    with patch("trustregistry.registry.registry_schemas.crud.get_schemas") as mock_crud:
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = [schema]
        result = await registry_schemas.get_schemas(db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock)
        assert result == [schema]


@pytest.mark.anyio
async def test_register_schema(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.create_schema"
    ) as mock_crud:
        schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = schema

        result = await registry_schemas.register_schema(schema_id, db_session_mock)
        mock_crud.assert_called_once_with(db_session_mock, schema=schema)
        assert result == schema


@pytest.mark.anyio
async def test_register_schema_already_exists(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.create_schema"
    ) as mock_crud:
        schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        mock_crud.side_effect = SchemaAlreadyExistsError("Schema already exists")
        with pytest.raises(HTTPException) as exc_info:
            await registry_schemas.register_schema(schema_id, db_session_mock)
        assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_register_cheqd_schema(db_session_mock):
    with (
        patch(
            "trustregistry.registry.registry_schemas.crud.create_schema"
        ) as mock_crud,
        patch(
            "trustregistry.registry.registry_schemas.resolve_cheqd_schema"
        ) as mock_resolve,
    ):
        schema_id = registry_schemas.SchemaID(
            schema_id="did:cheqd:testnet:123:schema:1.0"
        )
        mock_resolve.return_value = {
            "did": "did:cheqd:testnet:123",
            "name": "schema_name",
            "version": "1.0",
        }
        schema = Schema(
            did="did:cheqd:testnet:123",
            name="schema_name",
            version="1.0",
            id="did:cheqd:testnet:123:schema:1.0",
        )
        mock_crud.return_value = schema

        result = await registry_schemas.register_schema(schema_id, db_session_mock)
        mock_resolve.assert_called_once_with("did:cheqd:testnet:123:schema:1.0")
        mock_crud.assert_called_once_with(db_session_mock, schema=schema)
        assert result == schema


@pytest.mark.anyio
async def test_update_schema(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.update_schema"
    ) as mock_crud:
        new_schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:new_schema:1.0"
        )
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="new_schema",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:new_schema:1.0",
        )
        mock_crud.return_value = schema

        result = await registry_schemas.update_schema(
            "WgWxqztrNooG92RXvxSTWv:2:old_schema:1.0", new_schema_id, db_session_mock
        )
        mock_crud.assert_called_once_with(
            db_session_mock,
            schema=schema,
            schema_id="WgWxqztrNooG92RXvxSTWv:2:old_schema:1.0",
        )
        assert result == schema


@pytest.mark.anyio
async def test_update_schema_same_id(db_session_mock):
    new_schema_id = registry_schemas.SchemaID(
        schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
    )
    with pytest.raises(HTTPException) as exc_info:
        await registry_schemas.update_schema(
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0", new_schema_id, db_session_mock
        )
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_update_schema_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.update_schema"
    ) as mock_crud:
        new_schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:new_schema:1.0"
        )
        mock_crud.side_effect = SchemaDoesNotExistError("Schema not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_schemas.update_schema(
                "WgWxqztrNooG92RXvxSTWv:2:old_schema:1.0",
                new_schema_id,
                db_session_mock,
            )
        assert exc_info.value.status_code == 405


@pytest.mark.anyio
async def test_get_schema(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.get_schema_by_id"
    ) as mock_crud:
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = schema
        result = await registry_schemas.get_schema(
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0", db_session_mock
        )
        mock_crud.assert_called_once_with(
            db_session_mock, schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        assert result == schema


@pytest.mark.anyio
async def test_get_schema_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.get_schema_by_id"
    ) as mock_crud:
        mock_crud.side_effect = SchemaDoesNotExistError("Schema not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_schemas.get_schema(
                "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0", db_session_mock
            )
        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_remove_schema(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.delete_schema"
    ) as mock_crud:
        mock_crud.return_value = None
        result = await registry_schemas.remove_schema(
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0", db_session_mock
        )
        mock_crud.assert_called_once_with(
            db_session_mock, schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        assert result is None


@pytest.mark.anyio
async def test_remove_schema_not_found(db_session_mock):
    with patch(
        "trustregistry.registry.registry_schemas.crud.delete_schema"
    ) as mock_crud:
        mock_crud.side_effect = SchemaDoesNotExistError("Schema not found")
        with pytest.raises(HTTPException) as exc_info:
            await registry_schemas.remove_schema(
                "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0", db_session_mock
            )
        assert exc_info.value.status_code == 404


def test_get_schema_attrs():
    # Test non-cheqd schema
    schema_id = registry_schemas.SchemaID(
        schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
    )
    result = registry_schemas._get_schema_attrs(schema_id)
    assert result == ["WgWxqztrNooG92RXvxSTWv", "2", "schema_name", "1.0"]

    # Test cheqd schema
    cheqd_schema_id = registry_schemas.SchemaID(
        schema_id="did:cheqd:testnet:123:schema:1.0"
    )
    result = registry_schemas._get_schema_attrs(cheqd_schema_id)
    assert result == []
