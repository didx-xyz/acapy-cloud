from unittest.mock import patch

import pytest
from fastapi.exceptions import HTTPException

from shared.models.trustregistry import Schema
from trustregistry.crud import SchemaAlreadyExistsException, SchemaDoesNotExistException
from trustregistry.registry import registry_schemas


@pytest.mark.anyio
async def test_get_schemas():
    with patch("trustregistry.registry.registry_schemas.crud.get_schemas") as mock_crud:
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = [schema]
        result = await registry_schemas.get_schemas()
        mock_crud.assert_called_once()
        assert result == [schema]


@pytest.mark.anyio
async def test_register_schema():
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

        result = await registry_schemas.register_schema(schema_id)
        mock_crud.assert_called_once()
        assert result == schema


@pytest.mark.anyio
async def test_register_schema_cheqd():
    with (
        patch(
            "trustregistry.registry.registry_schemas.crud.create_schema"
        ) as mock_crud,
        patch(
            "trustregistry.registry.registry_schemas.resolve_cheqd_schema"
        ) as mock_resolve_cheqd,
    ):
        mock_resolve_cheqd.return_value = {
            "name": "schema_name",
            "version": "1.0",
        }
        schema_id = registry_schemas.SchemaID(
            schema_id=(
                "did:cheqd:testnet:9bf9286e-4f83-4138-b44e-62844e4cecc5/"
                "resources/2b7f3e8e-0187-4eca-a13a-fed3d7c711ab"
            )
        )
        schema = Schema(
            did="did:cheqd:testnet:9bf9286e-4f83-4138-b44e-62844e4cecc5",
            name="schema_name",
            version="1.0",
            id="did:cheqd:testnet:WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = schema

        result = await registry_schemas.register_schema(schema_id)
        mock_crud.assert_called_once()
        assert result == schema


@pytest.mark.anyio
async def test_register_schema_x():
    with patch(
        "trustregistry.registry.registry_schemas.crud.create_schema"
    ) as mock_crud:
        schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        mock_crud.side_effect = SchemaAlreadyExistsException()
        with pytest.raises(HTTPException) as ex:
            await registry_schemas.register_schema(schema_id)

        mock_crud.assert_called_once()
        assert ex.value.status_code == 409


@pytest.mark.anyio
@pytest.mark.parametrize(
    "schema_id, new_schema_id",
    [
        (
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
            registry_schemas.SchemaID(
                schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1"
            ),
        ),
        (
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1",
            registry_schemas.SchemaID(
                schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1"
            ),
        ),
    ],
)
async def test_update_schema(schema_id, new_schema_id):
    with patch(
        "trustregistry.registry.registry_schemas.crud.update_schema"
    ) as mock_crud:
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        if schema_id == new_schema_id.schema_id:
            with pytest.raises(HTTPException) as ex:
                await registry_schemas.update_schema(schema_id, new_schema_id)

            mock_crud.assert_not_called()
            assert ex.value.status_code == 400
        else:
            mock_crud.return_value = schema
            result = await registry_schemas.update_schema(schema_id, new_schema_id)
            mock_crud.assert_called_once()
            assert result == schema


@pytest.mark.anyio
async def test_update_schema_x():
    with patch(
        "trustregistry.registry.registry_schemas.crud.update_schema"
    ) as mock_crud:
        schema_id = "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        new_schema_id = registry_schemas.SchemaID(
            schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1"
        )
        mock_crud.side_effect = SchemaDoesNotExistException()
        with pytest.raises(HTTPException) as ex:
            await registry_schemas.update_schema(schema_id, new_schema_id)

        mock_crud.assert_called_once()
        assert ex.value.status_code == 405


@pytest.mark.anyio
async def test_get_schema_by_id():
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
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        mock_crud.assert_called_once()
        assert result == schema


@pytest.mark.anyio
async def test_get_schema_by_id_x():
    with patch(
        "trustregistry.registry.registry_schemas.crud.get_schema_by_id"
    ) as mock_crud:
        mock_crud.side_effect = SchemaDoesNotExistException()
        with pytest.raises(HTTPException) as ex:
            await registry_schemas.get_schema(
                "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
            )

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404


@pytest.mark.anyio
async def test_remove_schema():
    with patch(
        "trustregistry.registry.registry_schemas.crud.delete_schema"
    ) as mock_crud:
        schema = Schema(
            did="WgWxqztrNooG92RXvxSTWv",
            name="schema_name",
            version="1.0",
            id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
        )
        mock_crud.return_value = schema
        result = await registry_schemas.remove_schema(
            "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
        )
        mock_crud.assert_called_once()
        assert result is None


@pytest.mark.anyio
async def test_remove_schema_x():
    with patch(
        "trustregistry.registry.registry_schemas.crud.delete_schema"
    ) as mock_crud:
        mock_crud.side_effect = SchemaDoesNotExistException()
        with pytest.raises(HTTPException) as ex:
            await registry_schemas.remove_schema(
                "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
            )

        mock_crud.assert_called_once()
        assert ex.value.status_code == 404
