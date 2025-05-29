import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    ApiException,
    GetDIDEndpointResponse,
    GetSchemaResult,
    TAAInfo,
    TAARecord,
    TAAResult,
    TxnOrRegisterLedgerNymResponse,
)

from app.exceptions import CloudApiException
from app.services.acapy_ledger import (
    accept_taa,
    accept_taa_if_required,
    get_did_endpoint,
    get_taa,
    register_nym_on_ledger,
    schema_id_from_credential_definition_id,
)


@pytest.mark.anyio
async def test_get_taa_success(mock_agent_controller: AcaPyClient):
    taa_info = TAAInfo(taa_required=True, taa_record=TAARecord(digest="digest"))
    mock_agent_controller.ledger.fetch_taa.return_value = TAAResult(result=taa_info)

    result, mechanism = await get_taa(mock_agent_controller)
    assert result == taa_info
    assert mechanism == "service_agreement"


@pytest.mark.anyio
async def test_get_taa_failure(mock_agent_controller: AcaPyClient):
    mock_agent_controller.ledger.fetch_taa.return_value = TAAResult(
        result=TAAInfo(taa_required=True)
    )

    with pytest.raises(CloudApiException) as exc:
        await get_taa(mock_agent_controller)
    assert exc.value.status_code == 500
    assert "Something went wrong. Could not get TAA." in exc.value.detail


@pytest.mark.anyio
async def test_accept_taa_success(mock_agent_controller: AcaPyClient):
    taa_record = TAARecord(digest="digest")
    mock_agent_controller.ledger.accept_taa.return_value = None

    await accept_taa(mock_agent_controller, taa=taa_record, mechanism="data")
    mock_agent_controller.ledger.accept_taa.assert_called_once()


@pytest.mark.anyio
async def test_accept_taa_failure(mock_agent_controller: AcaPyClient):
    mock_agent_controller.ledger.accept_taa.side_effect = ApiException(status=500)

    with pytest.raises(CloudApiException) as exc:
        await accept_taa(
            mock_agent_controller, taa=TAARecord(digest=""), mechanism="data"
        )
    assert exc.value.status_code == 500
    assert "An unexpected error occurred while trying to accept TAA" in exc.value.detail


@pytest.mark.anyio
async def test_get_did_endpoint_success(mock_agent_controller: AcaPyClient):
    expected_response = GetDIDEndpointResponse(endpoint="http://example.com")
    mock_agent_controller.ledger.get_did_endpoint.return_value = expected_response

    response = await get_did_endpoint(mock_agent_controller, "data")
    assert response == expected_response


@pytest.mark.anyio
async def test_get_did_endpoint_failure(mock_agent_controller: AcaPyClient):
    mock_agent_controller.ledger.get_did_endpoint.return_value = None

    with pytest.raises(CloudApiException) as exc:
        await get_did_endpoint(mock_agent_controller, "data")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Could not obtain issuer endpoint."


@pytest.mark.anyio
async def test_register_nym_on_ledger_success(mock_agent_controller: AcaPyClient):
    expected_response = TxnOrRegisterLedgerNymResponse()
    mock_agent_controller.ledger.register_nym.return_value = expected_response

    response = await register_nym_on_ledger(
        mock_agent_controller,
        did="did",
        verkey="verkey",
        alias="alias",
        role="role",
        connection_id="conn_id",
        create_transaction_for_endorser="endorser",
    )
    assert response == expected_response


@pytest.mark.anyio
async def test_register_nym_on_ledger_failure(mock_agent_controller: AcaPyClient):
    mock_agent_controller.ledger.register_nym.side_effect = ApiException(status=500)

    with pytest.raises(CloudApiException) as exc:
        await register_nym_on_ledger(
            mock_agent_controller,
            did="did",
            verkey="verkey",
            alias="alias",
            role="role",
            connection_id="conn_id",
            create_transaction_for_endorser="endorser",
        )
    assert exc.value.status_code == 500
    assert "Error registering NYM on ledger" in exc.value.detail


@pytest.mark.anyio
async def test_accept_taa_if_required(mock_agent_controller: AcaPyClient):
    taa_info = TAAInfo(taa_required=True, taa_record=TAARecord(digest="digest"))
    mock_agent_controller.ledger.fetch_taa.return_value = TAAResult(result=taa_info)
    mock_agent_controller.ledger.accept_taa.return_value = None

    await accept_taa_if_required(mock_agent_controller)
    mock_agent_controller.ledger.accept_taa.assert_called_once()


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_seq_no_anoncreds(
    mock_agent_controller: AcaPyClient,
):
    schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"
    seq_no = "58279"
    cred_def_id_seq_no = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{seq_no}:tag"

    mock_agent_controller.anoncreds_schemas.get_schema.return_value = GetSchemaResult(
        schema_id=schema_id
    )

    schema_id_fetched = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_seq_no
    )

    assert schema_id_fetched == schema_id
    mock_agent_controller.anoncreds_schemas.get_schema.assert_called_once_with(
        schema_id=seq_no
    )


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_schema_id(
    mock_agent_controller: AcaPyClient,
):
    schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"
    cred_def_id_schema_id = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{schema_id}:tag"

    schema_id_fetched = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_schema_id
    )

    mock_agent_controller.schema.get_schema.assert_not_called()
    assert schema_id_fetched == schema_id


# TODO: Is this test still relevant?
# @pytest.mark.anyio
# async def test_schema_id_from_credential_definition_id_caching(
#     mock_agent_controller: AcaPyClient,
# ):
#     # Setup
#     schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"

#     # Test case 1: New format credential definition ID (8 tokens)
#     cred_def_id = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{schema_id}:tag"

#     # First call
#     result1 = await schema_id_from_credential_definition_id(
#         mock_agent_controller, cred_def_id
#     )
#     # Second call with same cred_def_id
#     result2 = await schema_id_from_credential_definition_id(
#         mock_agent_controller, cred_def_id
#     )

#     # Assert results are the same
#     assert result1 == result2
#     # Assert the schema was constructed from tokens (no API call)
#     assert result1 == schema_id
#     # Assert no API calls were made
#     mock_agent_controller.schema.get_schema.assert_not_called()

#     # Test case 2: Old format credential definition ID (5 tokens)
#     cred_def_id_old = "Ehx3RZSV38pn3MYvxtHhbQ:3:CL:456:tag2"

#     # Setup mock for old format
#     mock_agent_controller.schema.get_schema.return_value = SchemaGetResult(
#         var_schema=ModelSchema(id=schema_id)
#     )

#     # First call
#     result3 = await schema_id_from_credential_definition_id(
#         mock_agent_controller, cred_def_id_old
#     )
#     # Second call with same cred_def_id
#     result4 = await schema_id_from_credential_definition_id(
#         mock_agent_controller, cred_def_id_old
#     )

#     # Assert results are the same
#     assert result3 == result4
#     # Assert result matches mock schema ID
#     assert result3 == schema_id
#     # Assert API was called exactly once
#     mock_agent_controller.schema.get_schema.assert_called_once_with(schema_id="456")

#     # Reset mock for next test
#     mock_agent_controller.schema.get_schema.reset_mock()

#     # Test case 3: Different cred_def_id should trigger new API call
#     cred_def_id_old2 = "ABC123:3:CL:789:tag3"

#     # Setup mock for second old format
#     mock_agent_controller.schema.get_schema.return_value = SchemaGetResult(
#         var_schema=ModelSchema(id=schema_id)
#     )

#     await schema_id_from_credential_definition_id(
#         mock_agent_controller, cred_def_id_old2
#     )

#     # Assert both API calls were made
#     mock_agent_controller.schema.get_schema.assert_called_once_with(schema_id="789")


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_no_schema_askar_anoncreds(
    mock_agent_controller: AcaPyClient,
):
    seq_no = "58276"
    cred_def_id_seq_no = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{seq_no}:tag"

    mock_agent_controller.anoncreds_schemas.get_schema.return_value = GetSchemaResult(
        schema_id=None
    )

    with pytest.raises(CloudApiException) as exc:
        await schema_id_from_credential_definition_id(
            mock_agent_controller, cred_def_id_seq_no
        )

    assert exc.value.status_code == 404
    assert f"Schema with id {seq_no} not found." in exc.value.detail
