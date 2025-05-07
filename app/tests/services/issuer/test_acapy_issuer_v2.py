import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    V20CredAttrSpec,
    V20CredExRecord,
    V20CredExRecordAnonCreds,
    V20CredExRecordByFormat,
    V20CredExRecordDetail,
    V20CredExRecordListResult,
    V20CredPreview,
)

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.issuer import AnonCredsCredential, CredentialWithConnection
from app.services.issuer.acapy_issuer_v2 import IssuerV2
from app.tests.routes.issuer.test_create_offer import ld_cred

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
                attributes=[V20CredAttrSpec(name="speed", value="10")]
            ),
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864112",
            by_format=V20CredExRecordByFormat(
                cred_offer={
                    "anoncreds": {
                        "cred_def_id": cred_def_id_1,
                        "schema_id": schema_id_1,
                    }
                }
            ),
        ),
        anoncreds=V20CredExRecordAnonCreds(
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
                attributes=[V20CredAttrSpec(name="speed", value="10")]
            ),
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864133",
            by_format=V20CredExRecordByFormat(
                cred_offer={
                    "anoncreds": {
                        "cred_def_id": cred_def_id_2,
                        "schema_id": schema_id_2,
                    }
                }
            ),
        ),
        anoncreds=V20CredExRecordAnonCreds(
            created_at="2021-09-15 14:41:47Z",
            updated_at="2021-09-15 14:49:47Z",
            cred_ex_id="db9d7025-b276-4c32-ae38-fbad41864112",
            cred_id_stored="16c83f10-c205-4305-aa6f-cefa2d7da160",
        ),
    ),
]
v2_record = v2_credential_exchange_records[0]


@pytest.mark.anyio
async def test_get_records(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.get_records.return_value = (
        V20CredExRecordListResult(results=v2_credential_exchange_records)
    )

    records = await IssuerV2.get_records(mock_agent_controller)

    assert len(records) == len(v2_credential_exchange_records)
    assert {c.credential_exchange_id for c in records} == {
        f"v2-{v2_credential_exchange_records[0].cred_ex_record.cred_ex_id}",
        f"v2-{v2_credential_exchange_records[1].cred_ex_record.cred_ex_id}",
    }


@pytest.mark.anyio
async def test_get_records_empty(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.get_records.return_value = (
        V20CredExRecordListResult(results=[])
    )

    records = await IssuerV2.get_records(mock_agent_controller)

    assert len(records) == 0


@pytest.mark.anyio
async def test_get_records_with_query_params(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.get_records.return_value = (
        V20CredExRecordListResult(results=[v2_record])
    )

    records = await IssuerV2.get_records(
        mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=v2_record.cred_ex_record.connection_id,
        role=v2_record.cred_ex_record.role,
        state=v2_record.cred_ex_record.state,
        thread_id=v2_record.cred_ex_record.thread_id,
    )

    assert len(records) == 1
    assert {c.credential_exchange_id for c in records} == {
        f"v2-{v2_record.cred_ex_record.cred_ex_id}",
    }


@pytest.mark.anyio
async def test_get_record(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.get_record.return_value = v2_record

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


@pytest.mark.anyio
async def test_get_record_no_cred_ex_record(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.get_record.return_value = (
        V20CredExRecordDetail()
    )

    with pytest.raises(CloudApiException) as exc:
        await IssuerV2.get_record(
            mock_agent_controller,
            credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
        )

    assert exc.value.detail == "Record has no credential exchange record."
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_delete_credential_exchange(
    mock_agent_controller: AcaPyClient,
):
    cred_ex_record = v2_credential_exchange_records[1]

    mock_agent_controller.issue_credential_v2_0.delete_record.return_value = None
    await IssuerV2.delete_credential_exchange_record(
        mock_agent_controller,
        credential_exchange_id=cred_ex_record.cred_ex_record.cred_ex_id,
    )


@pytest.mark.anyio
async def test_send_credential(mock_agent_controller: AcaPyClient):
    credential = CredentialWithConnection(
        connection_id=v2_record.cred_ex_record.connection_id,
        anoncreds_credential_detail=AnonCredsCredential(
            credential_definition_id=cred_def_id_1,
            attributes={
                attr.name: attr.value
                for attr in v2_record.cred_ex_record.cred_preview.attributes
            },
        ),
    )

    issue_credential_v2_0 = mock_agent_controller.issue_credential_v2_0
    issue_credential_v2_0.issue_credential_automated.return_value = (
        v2_record.cred_ex_record
    )

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


@pytest.mark.anyio
async def test_send_credential_unsupported_cred_type(
    mock_agent_controller: AcaPyClient,
):
    credential = CredentialWithConnection(type="jwt", connection_id="abc")

    with pytest.raises(CloudApiException) as exc:
        await IssuerV2.send_credential(mock_agent_controller, credential)

    assert exc.value.detail == "Unsupported credential type: jwt"
    assert exc.value.status_code == 501


@pytest.mark.anyio
async def test_store_credential(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.store_credential.return_value = (
        v2_record
    )

    credential_exchange = await IssuerV2.store_credential(
        mock_agent_controller,
        credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
    )

    assert (
        credential_exchange.credential_exchange_id
        == f"v2-{v2_record.cred_ex_record.cred_ex_id}"
    )


@pytest.mark.anyio
async def test_store_credential_no_record(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.store_credential.return_value = (
        V20CredExRecordDetail()
    )

    with pytest.raises(CloudApiException) as exc:
        await IssuerV2.store_credential(
            mock_agent_controller,
            credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
        )

    assert exc.value.detail == "Stored record has no credential exchange record."
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_request_credential(mock_agent_controller: AcaPyClient):
    mock_agent_controller.issue_credential_v2_0.send_request.return_value = (
        v2_record.cred_ex_record
    )

    credential_exchange = await IssuerV2.request_credential(
        mock_agent_controller,
        credential_exchange_id=v2_record.cred_ex_record.cred_ex_id,
    )

    assert (
        credential_exchange.credential_exchange_id
        == f"v2-{v2_record.cred_ex_record.cred_ex_id}"
    )


@pytest.mark.anyio
async def test_create_offer_ld_proof(mock_agent_controller: AcaPyClient):
    credential = CredentialWithConnection(
        ld_credential_detail=ld_cred,
        connection_id="abc",
    )

    mock_agent_controller.issue_credential_v2_0.create_offer.return_value = (
        v2_record.cred_ex_record
    )
    result = await IssuerV2.create_offer(mock_agent_controller, credential)

    assert result.credential_exchange_id == f"v2-{v2_record.cred_ex_record.cred_ex_id}"


@pytest.mark.anyio
async def test_create_offer_anoncreds(mock_agent_controller: AcaPyClient):
    credential = CredentialWithConnection(
        anoncreds_credential_detail=AnonCredsCredential(
            credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
            issuer_did="WgWxqztrNooG92RXvxSTWv",
            attributes={"name": "Bob", "age": "25"},
        ),
        connection_id="abc",
    )

    mock_agent_controller.issue_credential_v2_0.create_offer.return_value = (
        v2_record.cred_ex_record
    )

    result = await IssuerV2.create_offer(mock_agent_controller, credential)

    assert result.credential_exchange_id == f"v2-{v2_record.cred_ex_record.cred_ex_id}"


@pytest.mark.anyio
async def test_create_offer_unsupported_credential_type(
    mock_agent_controller: AcaPyClient,
):
    credential = CredentialWithConnection(type="jwt", connection_id="abc")

    with pytest.raises(CloudApiException) as exc:
        await IssuerV2.create_offer(mock_agent_controller, credential)

    assert exc.value.detail == "Unsupported credential type: jwt"
    assert exc.value.status_code == 501
