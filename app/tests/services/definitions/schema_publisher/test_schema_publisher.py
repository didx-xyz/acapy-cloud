from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import (
    ModelSchema,
    SchemaGetResult,
    SchemaSendRequest,
    SchemaSendResult,
    TxnOrSchemaSendResult,
)

from app.exceptions import CloudApiException
from app.models.definitions import CredentialSchema
from app.services.definitions.schema_publisher import SchemaPublisher

# pylint: disable=redefined-outer-name
# because re-using fixtures in same module
# pylint: disable=protected-access
# because we are testing protected methods


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_controller():
    return AsyncMock()


@pytest.fixture
def publisher(mock_controller, mock_logger):
    return SchemaPublisher(mock_controller, mock_logger)


sample_schema_id = "CXQseFxV34pcb8vf32XhEa:2:test_schema:1.0"
sample_schema_name = "test_schema"
sample_schema_version = "1.0"
sample_attribute_names = ["attr1", "attr2"]

schemas_send_request = SchemaSendRequest(
    schema_name=sample_schema_name,
    schema_version=sample_schema_version,
    attributes=sample_attribute_names,
)
schema_send_result = TxnOrSchemaSendResult(
    sent=SchemaSendResult(
        schema_id=sample_schema_id,
        var_schema=ModelSchema(
            id=sample_schema_id,
            name=sample_schema_name,
            version=sample_schema_version,
            attr_names=sample_attribute_names,
        ),
    )
)
schema_get_result = SchemaGetResult(
    var_schema=ModelSchema(
        id=sample_schema_id,
        name=sample_schema_name,
        version=sample_schema_version,
        attr_names=sample_attribute_names,
    )
)
credential_schema = CredentialSchema(
    id=sample_schema_id,
    name=sample_schema_name,
    version=sample_schema_version,
    attribute_names=sample_attribute_names,
)


@pytest.mark.anyio
async def test_publish_schema_success(publisher):
    mock_schema_request = schemas_send_request
    mock_result = schema_send_result
    final_result = credential_schema
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ), patch(
        "app.services.definitions.schema_publisher.register_schema"
    ) as mock_register_schema:
        result = await publisher.publish_schema(mock_schema_request)

        assert result == final_result
        mock_register_schema.assert_called_once_with(
            schema_id="CXQseFxV34pcb8vf32XhEa:2:test_schema:1.0", schema_type="indy"
        )


@pytest.mark.anyio
async def test_publish_schema_already_exists(publisher):
    mock_schema_request = schemas_send_request
    mock_existing_schema = credential_schema

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            CloudApiException(detail="already exist", status_code=400),
            mock_existing_schema,
        ],
    ), patch.object(
        publisher, "_handle_existing_schema", return_value=mock_existing_schema
    ):
        result = await publisher.publish_schema(mock_schema_request)

        assert result == mock_existing_schema


@pytest.mark.anyio
async def test_publish_schema_unhandled_exception(publisher):
    mock_schema_request = schemas_send_request

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=CloudApiException(detail="Unhandled error", status_code=500),
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_schema(mock_schema_request)

        assert "Error while creating schema." in str(exc_info.value)


@pytest.mark.anyio
async def test_publish_schema_no_schema_id(publisher):
    mock_schema_request = schemas_send_request
    mock_result = TxnOrSchemaSendResult(sent=None)

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_schema(mock_schema_request)

        assert "An unexpected error occurred: could not publish schema." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_handle_existing_schema_success(publisher):
    mock_schema_request = schemas_send_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema = schema_get_result
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema],
    ), patch(
        "app.services.definitions.schema_publisher.credential_schema_from_acapy",
        return_value=MagicMock(spec=CredentialSchema),
    ):
        result = await publisher._handle_existing_schema(mock_schema_request)

        assert isinstance(result, CredentialSchema)


@pytest.mark.anyio
async def test_handle_existing_schema_different_attributes(publisher):
    mock_schema_request = schemas_send_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema = SchemaGetResult(
        var_schema=ModelSchema(
            attr_names=["attr1", "attr3"],
            id=sample_schema_id,
            name=sample_schema_name,
            version=sample_schema_version,
        )
    )
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema],
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher._handle_existing_schema(mock_schema_request)

        assert "Schema already exists with different attribute names" in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_handle_existing_schema_changed_did(publisher):
    mock_schema_request = schemas_send_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = SchemaGetResult(var_schema=None)
    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = ["schema_id_1"]

    mock_schema = schema_get_result
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            mock_pub_did,
            mock_schema_none,
            mock_schemas_created_ids,
            mock_schema,
        ],
    ), patch(
        "app.services.definitions.schema_publisher.credential_schema_from_acapy",
        return_value=MagicMock(spec=CredentialSchema),
    ):
        result = await publisher._handle_existing_schema(mock_schema_request)

        assert isinstance(result, CredentialSchema)


@pytest.mark.anyio
async def test_handle_existing_schema_no_schemas_found(publisher):
    mock_schema_request = schemas_send_request

    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = MagicMock(spec=SchemaGetResult)
    mock_schema_none.var_schema = None

    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = []

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema_none, mock_schemas_created_ids],
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher._handle_existing_schema(mock_schema_request)

        assert str(exc_info.value) == "500: Could not publish schema."
        assert exc_info.value.status_code == 500


@pytest.mark.anyio
async def test_handle_existing_schema_multiple_schemas_found(publisher):
    mock_schema_request = schemas_send_request

    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = MagicMock(spec=SchemaGetResult)
    mock_schema_none.var_schema = None

    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = [
        sample_schema_id,
        "aeXh23fv8bp43VxFesQXC:2:test_schema:1.0",
    ]
    mock_schemas = [
        SchemaGetResult(
            var_schema=ModelSchema(
                id=sample_schema_id,
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=sample_attribute_names,
            )
        ),
        SchemaGetResult(
            var_schema=ModelSchema(
                id="aeXh23fv8bp43VxFesQXC:2:test_schema:1.0",
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=["attr3", "attr4"],
            )
        ),
    ]
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            mock_pub_did,
            mock_schema_none,
            mock_schemas_created_ids,
            mock_schemas[0],
            mock_schemas[1],
        ],
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher._handle_existing_schema(mock_schema_request)

        assert str(exc_info.value).startswith(
            "409: Multiple schemas with name test_schema"
        )
        assert exc_info.value.status_code == 409
