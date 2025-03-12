import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    ApiException,
    ModelSchema,
    SchemaGetResult,
    TAAAccept,
    TAAInfo,
    TAARecord,
    TAAResult,
)
from assertpy import assert_that
from fastapi import HTTPException
from mockito import verify, when

from app.exceptions import CloudApiException
from app.services.acapy_ledger import (
    accept_taa,
    get_did_endpoint,
    get_taa,
    schema_id_from_credential_definition_id,
)
from app.tests.util.mock import to_async


@pytest.mark.anyio
async def test_error_on_get_taa(mock_agent_controller: AcaPyClient):
    when(mock_agent_controller.ledger).fetch_taa().thenReturn(
        to_async(TAAResult(result=TAAInfo(taa_required=True)))
    )

    with pytest.raises(HTTPException) as exc:
        await get_taa(mock_agent_controller)
    assert exc.value.status_code == 500
    assert "Something went wrong. Could not get TAA." in exc.value.detail


@pytest.mark.anyio
async def test_error_on_accept_taa(mock_agent_controller: AcaPyClient):
    when(mock_agent_controller.ledger).accept_taa(
        body=TAAAccept(mechanism="data", text=None, version=None)
    ).thenRaise(ApiException(status=500))

    with pytest.raises(CloudApiException) as exc:
        await accept_taa(
            mock_agent_controller, taa=TAARecord(digest=""), mechanism="data"
        )
    assert exc.value.status_code == 500
    assert "An unexpected error occurred while trying to accept TAA" in exc.value.detail


@pytest.mark.anyio
async def test_error_on_get_did_endpoint(mock_agent_controller: AcaPyClient):
    when(mock_agent_controller.ledger).get_did_endpoint(did="data").thenReturn(
        to_async(None)
    )

    with pytest.raises(HTTPException) as exc:
        await get_did_endpoint(mock_agent_controller, "data")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Could not obtain issuer endpoint."


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_seq_no(
    mock_agent_controller: AcaPyClient,
):
    schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"
    seq_no = "58278"
    cred_def_id_seq_no = "Ehx3RZSV38pn3MYvxtHhbQ:3:CL:58278:tag"

    when(mock_agent_controller.schema).get_schema(schema_id=seq_no).thenReturn(
        to_async(
            SchemaGetResult(
                var_schema=ModelSchema(
                    id=schema_id,
                )
            )
        )
    )

    schema_id = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_seq_no, "askar"
    )

    assert_that(schema_id).is_equal_to(schema_id)
    verify(mock_agent_controller.schema).get_schema(schema_id=seq_no)


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_schema_id(
    mock_agent_controller: AcaPyClient,
):
    schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"
    cred_def_id_schema_id = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{schema_id}:tag"

    when(mock_agent_controller.schema).get_schema(...)

    schema_id = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_schema_id, "askar"
    )

    verify(mock_agent_controller.schema, times=0).get_schema(...)
    assert_that(schema_id).is_equal_to(schema_id)


@pytest.mark.anyio
async def test_schema_id_from_credential_definition_id_caching(
    mock_agent_controller: AcaPyClient,
):
    # Setup
    schema_id = "Ehx3RZSV38pn3MYvxtHhbQ:2:schema_name:1.0.1"

    # Test case 1: New format credential definition ID (8 tokens)
    cred_def_id = f"Ehx3RZSV38pn3MYvxtHhbQ:3:CL:{schema_id}:tag"

    # First call
    result1 = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id, "askar"
    )
    # Second call with same cred_def_id
    result2 = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id, "askar"
    )

    # Assert results are the same
    assert_that(result1).is_equal_to(result2)
    # Assert the schema was constructed from tokens (no API call)
    assert_that(result1).is_equal_to(schema_id)
    # Assert no API calls were made
    verify(mock_agent_controller.schema, times=0).get_schema(...)

    # Test case 2: Old format credential definition ID (5 tokens)
    cred_def_id_old = "Ehx3RZSV38pn3MYvxtHhbQ:3:CL:456:tag2"

    # Setup mock for old format
    when(mock_agent_controller.schema).get_schema(schema_id="456").thenReturn(
        to_async(
            SchemaGetResult(
                var_schema=ModelSchema(
                    id=schema_id,
                )
            )
        )
    )

    # First call
    result3 = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_old, "askar"
    )
    # Second call with same cred_def_id
    result4 = await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_old, "askar"
    )

    # Assert results are the same
    assert_that(result3).is_equal_to(result4)
    # Assert result matches mock schema ID
    assert_that(result3).is_equal_to(schema_id)
    # Assert API was called exactly once
    verify(mock_agent_controller.schema).get_schema(schema_id="456")

    # Test case 3: Different cred_def_id should trigger new API call
    cred_def_id_old2 = "ABC123:3:CL:789:tag3"

    # Setup mock for second old format
    when(mock_agent_controller.schema).get_schema(schema_id="789").thenReturn(
        to_async(
            SchemaGetResult(
                var_schema=ModelSchema(
                    id=schema_id,
                )
            )
        )
    )

    await schema_id_from_credential_definition_id(
        mock_agent_controller, cred_def_id_old2, "askar"
    )

    # Assert both API calls were made
    verify(mock_agent_controller.schema).get_schema(schema_id="456")
    verify(mock_agent_controller.schema).get_schema(schema_id="789")
