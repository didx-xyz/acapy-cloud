import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import (
    AnonCredsSchema,
    GetSchemaResult,
    SchemaPostRequest,
    SchemaResult,
    SchemaState,
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
def publisher(mock_controller, mock_logger) -> SchemaPublisher:
    return SchemaPublisher(mock_controller, mock_logger)


sample_issuer_id = "CXQseFxV34pcb8vf32XhEa"
sample_schema_name = "test_schema"
sample_schema_version = "1.0"
sample_schema_id = f"{sample_issuer_id}:2:{sample_schema_name}:{sample_schema_version}"
sample_attribute_names = ["attr1", "attr2"]

sample_anoncreds_schema = AnonCredsSchema(
    name=sample_schema_name,
    version=sample_schema_version,
    attr_names=sample_attribute_names,
    issuer_id=sample_issuer_id,
)

anoncreds_schema_request = SchemaPostRequest(
    var_schema=sample_anoncreds_schema,
)
anoncreds_schema_result = SchemaResult(
    schema_state=SchemaState(
        state="finished", schema_id=sample_schema_id, var_schema=sample_anoncreds_schema
    ),
)
anoncreds_get_schema_result = GetSchemaResult(
    schema_id=sample_schema_id,
    var_schema=sample_anoncreds_schema,
)
credential_schema = CredentialSchema(
    id=sample_schema_id,
    name=sample_schema_name,
    version=sample_schema_version,
    attribute_names=sample_attribute_names,
)


@pytest.mark.anyio
async def test_publish_anoncreds_schema_success(publisher):
    final_result = credential_schema
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=anoncreds_schema_result,
    ), patch(
        "app.services.definitions.schema_publisher.register_schema"
    ) as mock_register_schema:
        result = await publisher.publish_anoncreds_schema(anoncreds_schema_request)

        assert result == final_result
        mock_register_schema.assert_called_once_with(
            schema_id=sample_schema_id, schema_type="anoncreds"
        )


@pytest.mark.anyio
async def test_publish_anoncreds_schema_already_exists(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_existing_schema = credential_schema

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            CloudApiException(detail="already exist", status_code=400),
            mock_existing_schema,
        ],
    ), patch.object(
        publisher,
        "_handle_existing_anoncreds_schema",
        return_value=mock_existing_schema,
    ):
        result = await publisher.publish_anoncreds_schema(mock_schema_request)

        assert result == mock_existing_schema


@pytest.mark.anyio
async def test_publish_anoncreds_schema_unhandled_exception(publisher):
    mock_schema_request = anoncreds_schema_request

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=CloudApiException(detail="Unhandled error", status_code=500),
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_anoncreds_schema(mock_schema_request)

        assert "Error while creating schema." in str(exc_info.value)


@pytest.mark.anyio
async def test_publish_anoncreds_schema_no_schema_id(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_result = SchemaResult(
        schema_state=SchemaState(
            state="finished", schema_id=None, var_schema=sample_anoncreds_schema
        ),
    )

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_anoncreds_schema(mock_schema_request)

        assert "An unexpected error occurred: could not publish schema." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_publish_anoncreds_schema_timeout_error(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_result = SchemaResult(
        schema_state=SchemaState(
            state="wait", schema_id=sample_schema_id, var_schema=sample_anoncreds_schema
        ),
        registration_metadata={"txn": {"transaction_id": "txn_id"}},
    )

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ), patch(
        "app.services.definitions.schema_publisher.coroutine_with_retry_until_value",
        side_effect=asyncio.TimeoutError,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_anoncreds_schema(mock_schema_request)

        assert "Timed out waiting for schema to be published." in str(exc_info.value)


@pytest.mark.anyio
async def test_publish_anoncreds_schema_missing_transaction_id(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_result = SchemaResult(
        schema_state=SchemaState(
            state="wait", schema_id=sample_schema_id, var_schema=sample_anoncreds_schema
        ),
        registration_metadata={},
    )

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_anoncreds_schema(mock_schema_request)

        assert "Could not publish schema. No transaction id found in response." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_publish_anoncreds_schema_unexpected_state(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_result = SchemaResult(
        schema_state=SchemaState(
            state="failed",
            schema_id=sample_schema_id,
            var_schema=sample_anoncreds_schema,
        ),
    )

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        return_value=mock_result,
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher.publish_anoncreds_schema(mock_schema_request)

        assert "An unexpected error occurred: could not publish schema." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_success(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema = anoncreds_get_schema_result
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema],
    ), patch(
        "app.services.definitions.schema_publisher.anoncreds_credential_schema",
        return_value=MagicMock(spec=CredentialSchema),
    ):
        result = await publisher._handle_existing_anoncreds_schema(mock_schema_request)

        assert isinstance(result, CredentialSchema)


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_different_attributes(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema = GetSchemaResult(
        schema_id=sample_schema_id,
        var_schema=AnonCredsSchema(
            name=sample_schema_name,
            version=sample_schema_version,
            attr_names=["attr1", "attr3"],
            issuer_id=sample_issuer_id,
        ),
    )
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema],
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher._handle_existing_anoncreds_schema(mock_schema_request)

        assert "Schema already exists with different attribute names" in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_changed_did(publisher):
    mock_schema_request = anoncreds_schema_request
    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = GetSchemaResult(
        var_schema=AnonCredsSchema(
            name=sample_schema_name,
            version=sample_schema_version,
            attr_names=sample_attribute_names,
            issuer_id="test_did",
        )
    )
    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = ["schema_id_1"]

    mock_schema = anoncreds_schema_result
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            mock_pub_did,
            mock_schema_none,
            mock_schemas_created_ids,
            mock_schema,
        ],
    ), patch(
        "app.services.definitions.schema_publisher.anoncreds_credential_schema",
        return_value=MagicMock(spec=CredentialSchema),
    ):
        result = await publisher._handle_existing_anoncreds_schema(mock_schema_request)

        assert isinstance(result, CredentialSchema)


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_no_schemas_found(publisher):
    mock_schema_request = anoncreds_schema_request

    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = GetSchemaResult(var_schema=None)
    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = []

    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[mock_pub_did, mock_schema_none, mock_schemas_created_ids],
    ):
        with pytest.raises(CloudApiException) as exc_info:
            await publisher._handle_existing_anoncreds_schema(mock_schema_request)

        assert str(exc_info.value) == "500: Could not publish schema."
        assert exc_info.value.status_code == 500


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_multiple_schemas_found(publisher):
    mock_schema_request = anoncreds_schema_request

    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = GetSchemaResult(var_schema=None)
    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = [
        sample_schema_id,
        "aeXh23fv8bp43VxFesQXC:2:test_schema:1.0",
    ]
    mock_schemas = [
        GetSchemaResult(
            schema_id=sample_schema_id,
            var_schema=AnonCredsSchema(
                issuer_id=sample_issuer_id,
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=sample_attribute_names,
            ),
        ),
        GetSchemaResult(
            schema_id="aeXh23fv8bp43VxFesQXC:2:test_schema:1.0",
            var_schema=AnonCredsSchema(
                issuer_id="aeXh23fv8bp43VxFesQXC",
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=["attr3", "attr4"],
            ),
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
            await publisher._handle_existing_anoncreds_schema(mock_schema_request)

        assert str(exc_info.value).startswith(
            "409: Multiple schemas with name test_schema"
        )
        assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_handle_existing_anoncreds_schema_new_did_one_schema_found(publisher):
    mock_schema_request = anoncreds_schema_request

    mock_pub_did = MagicMock()
    mock_pub_did.result.did = "test_did"

    mock_schema_none = GetSchemaResult(var_schema=None)
    mock_schemas_created_ids = MagicMock()
    mock_schemas_created_ids.schema_ids = [sample_schema_id]
    mock_schemas = [
        GetSchemaResult(
            schema_id=sample_schema_id,
            var_schema=AnonCredsSchema(
                issuer_id=sample_issuer_id,
                name=sample_schema_name,
                version=sample_schema_version,
                attr_names=sample_attribute_names,
            ),
        )
    ]
    with patch(
        "app.services.definitions.schema_publisher.handle_acapy_call",
        side_effect=[
            mock_pub_did,
            mock_schema_none,
            mock_schemas_created_ids,
            mock_schemas[0],
        ],
    ):
        result = await publisher._handle_existing_anoncreds_schema(mock_schema_request)
        assert result == credential_schema
