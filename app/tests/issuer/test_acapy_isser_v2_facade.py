from typing import Any, Optional

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    V10CredentialStoreRequest,
    V20CredAttrSpec,
    V20CredExRecord,
    V20CredExRecordByFormat,
    V20CredExRecordDetail,
    V20CredExRecordIndy,
    V20CredExRecordListResult,
    V20CredPreview,
    V20CredRequestRequest,
)
from assertpy import assert_that
from generic.issuer.facades.acapy_issuer_v2 import IssuerV2
from generic.issuer.models import Credential
from mockito import when


# need this to handle the async with the mock
async def get(response: Optional[Any] = None):
    if response:
        return response


schema_id_1 = "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
cred_def_id_1 = "WgWxqztrNooG92RXvxSTWv:3:CL:20:tag1"

schema_id_2 = "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1"
cred_def_id_2 = "WgWxqztrNooG92RXvxSTWv:3:CL:20:tag2"


v2_credential_exchange_records = [
    V20CredExRecordDetail(
        cred_ex_record=V20CredExRecord(
            created_at="2021-09-15 14:41:47Z",
            role="issuer",
            updated_at="2021-09-15 14:49:47Z",
            state="offer-sent",
            connection_id="3fa85f64-5717-4562-b3fc-2c963f66afb9",
            cred_preview=V20CredPreview(
                attributes=[V20CredAttrSpec(name="speed", value="fasts")]
            ),
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864112",
            by_format=V20CredExRecordByFormat(
                cred_offer={
                    "indy": {
                        "cred_def_id": cred_def_id_1,
                        "schema_id": schema_id_1,
                    }
                }
            ),
        ),
        indy=V20CredExRecordIndy(
            created_at="2021-09-15 14:41:47Z",
            updated_at="2021-09-15 14:49:47Z",
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864112",
        ),
    ),
    V20CredExRecordDetail(
        cred_ex_record=V20CredExRecord(
            created_at="2021-09-15 14:41:47Z",
            role="holder",
            updated_at="2021-09-15 14:49:47Z",
            state="offer-sent",
            connection_id="3fa85f64-5717-4562-b3fc-2c963f6dafb9",
            cred_preview=V20CredPreview(
                attributes=[V20CredAttrSpec(name="speed", value="average")]
            ),
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864133",
            by_format=V20CredExRecordByFormat(
                cred_offer={
                    "indy": {
                        "cred_def_id": cred_def_id_2,
                        "schema_id": schema_id_2,
                    }
                }
            ),
        ),
        indy=V20CredExRecordIndy(
            created_at="2021-09-15 14:41:47Z",
            updated_at="2021-09-15 14:49:47Z",
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864112",
            cred_id_stored="16c83f10-c205-4305-aa6f-cefa2d7da160",
        ),
    ),
]


@pytest.mark.asyncio
async def test_get_records(mock_agent_controller: AcaPyClient):
    when(mock_agent_controller.issue_credential_v2_0).get_records(...).thenReturn(
        get(V20CredExRecordListResult(results=v2_credential_exchange_records))
    )

    records = await IssuerV2.get_records(mock_agent_controller)

    assert len(records) == len(v2_credential_exchange_records)
    assert_that(map(lambda c: c.credential_id, records)).contains(
        f"v2-{v2_credential_exchange_records[0].cred_ex_record.cred_ex_id}",
        f"v2-{v2_credential_exchange_records[1].cred_ex_record.cred_ex_id}",
    )


@pytest.mark.asyncio
async def test_get_records_connection_id(mock_agent_controller: AcaPyClient):
    v2_record = v2_credential_exchange_records[0]

    when(mock_agent_controller.issue_credential_v2_0).get_records(
        connection_id=v2_record.cred_ex_record.connection_id
    ).thenReturn(get(V20CredExRecordListResult(results=[v2_record])))

    records = await IssuerV2.get_records(
        mock_agent_controller, connection_id=v2_record.cred_ex_record.connection_id
    )

    assert len(records) == 1
    assert_that(map(lambda c: c.credential_id, records)).contains(
        f"v2-{v2_record.cred_ex_record.cred_ex_id}",
    )


@pytest.mark.asyncio
async def test_get_record(mock_agent_controller: AcaPyClient):
    v2_record = v2_credential_exchange_records[0]

    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=v2_record.cred_ex_record.cred_ex_id
    ).thenReturn(get(v2_record))

    record = await IssuerV2.get_record(
        mock_agent_controller,
        credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
    )

    assert record.credential_definition_id == cred_def_id_1
    assert record.schema_id == schema_id_1
    assert record.created_at == v2_record.cred_ex_record.created_at
    assert record.role == v2_record.cred_ex_record.role
    assert record.updated_at == v2_record.cred_ex_record.updated_at
    assert record.state == "offer-sent"
    assert record.connection_id == v2_record.cred_ex_record.connection_id
    assert record.attributes == {
        attr.name: attr.value
        for attr in v2_record.cred_ex_record.cred_preview.attributes
    }


@pytest.mark.asyncio
async def test_delete_credential_exchange_with_credential(
    mock_agent_controller: AcaPyClient,
):
    with_credential_id = v2_credential_exchange_records[1]

    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=with_credential_id.cred_ex_record.cred_ex_id
    ).thenReturn(get(with_credential_id))
    when(mock_agent_controller.issue_credential_v2_0).delete_record(
        cred_ex_id=with_credential_id.cred_ex_record.cred_ex_id
    ).thenReturn(get())
    when(mock_agent_controller.credentials).delete_record(
        credential_id=with_credential_id.indy.cred_id_stored
    ).thenReturn(get())
    await IssuerV2.delete_credential(
        mock_agent_controller,
        credential_exchange_id=with_credential_id.cred_ex_record.cred_ex_id,
    )


@pytest.mark.asyncio
async def test_delete_credential_exchange_without_credential(
    mock_agent_controller: AcaPyClient,
):
    without_credential_id = v2_credential_exchange_records[0]
    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=without_credential_id.cred_ex_record.cred_ex_id
    ).thenReturn(get(without_credential_id))
    when(mock_agent_controller.issue_credential_v2_0).delete_record(
        cred_ex_id=without_credential_id.cred_ex_record.cred_ex_id
    ).thenReturn(get())
    await IssuerV2.delete_credential(
        mock_agent_controller,
        credential_exchange_id=without_credential_id.cred_ex_record.cred_ex_id,
    )


@pytest.mark.asyncio
async def test_send_credential(mock_agent_controller: AcaPyClient):
    v2_record = v2_credential_exchange_records[0]

    credential = Credential(
        connection_id=v2_record.cred_ex_record.connection_id,
        cred_def_id=cred_def_id_1,
        attributes={
            attr.name: attr.value
            for attr in v2_record.cred_ex_record.cred_preview.attributes
        },
    )

    when(mock_agent_controller.issue_credential_v2_0).issue_credential_automated(
        ...,
    ).thenReturn(get(v2_record.cred_ex_record))

    credential_exchange = await IssuerV2.send_credential(
        mock_agent_controller, credential
    )

    assert credential_exchange.credential_definition_id == cred_def_id_1
    assert credential_exchange.created_at == v2_record.cred_ex_record.created_at
    assert credential_exchange.role == v2_record.cred_ex_record.role
    assert credential_exchange.updated_at == v2_record.cred_ex_record.updated_at
    assert credential_exchange.schema_id == schema_id_1
    assert credential_exchange.state == "offer-sent"
    assert credential_exchange.connection_id == v2_record.cred_ex_record.connection_id
    assert credential_exchange.attributes == {
        attr.name: attr.value
        for attr in v2_record.cred_ex_record.cred_preview.attributes
    }


@pytest.mark.asyncio
async def test_store_credential(mock_agent_controller: AcaPyClient):
    v2_record = v2_credential_exchange_records[0]

    when(mock_agent_controller.issue_credential_v2_0).store_credential(
        cred_ex_id=v2_record.cred_ex_record.cred_ex_id,
        body=V10CredentialStoreRequest(credential_id=None),
    ).thenReturn(get(v2_record))

    credential_exchange = await IssuerV2.store_credential(
        mock_agent_controller,
        credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
    )

    assert (
        credential_exchange.credential_id == f"v2-{v2_record.cred_ex_record.cred_ex_id}"
    )


@pytest.mark.asyncio
async def test_request_credential(mock_agent_controller: AcaPyClient):
    v2_record = v2_credential_exchange_records[0]

    when(mock_agent_controller.issue_credential_v2_0).send_request(
        cred_ex_id=v2_record.cred_ex_record.cred_ex_id,
        body=V20CredRequestRequest(holder_did=None),
    ).thenReturn(get(v2_record.cred_ex_record))

    credential_exchange = await IssuerV2.request_credential(
        mock_agent_controller,
        credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
    )

    assert (
        credential_exchange.credential_id == f"v2-{v2_record.cred_ex_record.cred_ex_id}"
    )
