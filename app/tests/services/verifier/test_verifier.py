from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import AcaPyClient, ConnRecord, IndyCredInfo, IndyCredPrecis
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

import app.routes.verifier as test_module
from app.dependencies.auth import AcaPyAuth
from app.exceptions.cloudapi_exception import CloudApiException
from app.main import app
from app.models.verifier import CredInfo, CredPrecis
from app.routes.verifier import acapy_auth_from_header, get_credentials_by_proof_id
from app.services.verifier.acapy_verifier_v2 import VerifierV2
from app.tests.services.verifier.utils import (
    anoncreds_pres_spec,
    sample_anoncreds_proof_request,
)
from app.util import acapy_verifier_utils
from shared.models.presentation_exchange import PresentationExchange
from shared.models.trustregistry import Actor
from shared.util.mock_agent_controller import MockContextManagedController

presentation_exchange_record = PresentationExchange(
    connection_id="abcde",
    created_at="2021-11-22 11:37:45.179595Z",
    updated_at="2021-11-22 11:37:45.179595Z",
    proof_id="abcde",
    presentation=None,
    role="prover",
    state="presentation-sent",
    verified=False,
)

actor = Actor(
    id="abcde",
    name="Flint",
    roles=["verifier"],
    did="did:sov:2cpBmR3FqGKWi5EyUbpRY8",
    didcomm_invitation=None,
)
conn_record = ConnRecord(
    connection_id="abcde",
    invitation_key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV",
)


@pytest.mark.anyio
async def test_send_proof_request_v2(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mock_agent_controller.connection.get_connection.return_value = conn_record

    mock_agent_controller.wallet.get_public_did.side_effect = CloudApiException(
        "No did"
    )

    send_proof_request = test_module.SendProofRequest(
        connection_id="abcde",
        anoncreds_proof_request=sample_anoncreds_proof_request(),
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )
    mocker.patch.object(
        VerifierV2, "send_proof_request", return_value=presentation_exchange_record
    )
    mocker.patch.object(acapy_verifier_utils, "get_actor", return_value=actor)

    result = await test_module.send_proof_request(
        body=send_proof_request,
        auth=mock_tenant_auth,
    )

    assert result is presentation_exchange_record
    VerifierV2.send_proof_request.assert_called_once_with(
        controller=mock_agent_controller, send_proof_request=send_proof_request
    )


@pytest.mark.anyio
async def test_send_proof_request_v2_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        VerifierV2, "send_proof_request", side_effect=CloudApiException("ERROR")
    )
    mocker.patch.object(test_module, "assert_valid_verifier", return_value=None)

    send_proof_request = test_module.SendProofRequest(
        connection_id="abcde",
        anoncreds_proof_request=sample_anoncreds_proof_request(),
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    with pytest.raises(CloudApiException, match="500: ERROR") as exc:
        await test_module.send_proof_request(
            body=send_proof_request,
            auth=mock_tenant_auth,
        )
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_send_proof_request_v2_no_response(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(VerifierV2, "send_proof_request", return_value=None)

    mocker.patch.object(
        test_module,
        "assert_valid_verifier",
        return_value=None,
    )

    send_proof_request = test_module.SendProofRequest(
        connection_id="abcde",
        anoncreds_proof_request=sample_anoncreds_proof_request(),
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    result = await test_module.send_proof_request(
        body=send_proof_request, auth=mock_tenant_auth
    )

    assert result is None
    VerifierV2.send_proof_request.assert_called_once_with(
        controller=mock_agent_controller, send_proof_request=send_proof_request
    )


@pytest.mark.anyio
async def test_create_proof_request(
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        VerifierV2, "create_proof_request", return_value=presentation_exchange_record
    )
    result = await test_module.create_proof_request(
        body=test_module.CreateProofRequest(
            anoncreds_proof_request=sample_anoncreds_proof_request(),
            connection_id="abcde",
        ),
        auth=mock_tenant_auth,
    )
    assert result is presentation_exchange_record


@pytest.mark.anyio
async def test_create_proof_request_exception(
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        VerifierV2, "create_proof_request", side_effect=CloudApiException("ERROR")
    )
    with pytest.raises(CloudApiException, match="500: ERROR") as exc:
        await test_module.create_proof_request(
            body=test_module.CreateProofRequest(
                anoncreds_proof_request=sample_anoncreds_proof_request(),
                connection_id="abcde",
            ),
            auth=mock_tenant_auth,
        )
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_create_proof_request_no_result(
    mock_tenant_auth: AcaPyAuth, mocker: MockerFixture
):
    mocker.patch.object(VerifierV2, "create_proof_request", return_value=None)
    result = await test_module.create_proof_request(
        body=test_module.CreateProofRequest(
            anoncreds_proof_request=sample_anoncreds_proof_request(),
            connection_id="abcde",
        ),
        auth=mock_tenant_auth,
    )
    assert result is None


@pytest.mark.anyio
async def test_accept_proof_request_v2(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        VerifierV2, "accept_proof_request", return_value=presentation_exchange_record
    )
    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v2-1234", anoncreds_presentation_spec=anoncreds_pres_spec
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        test_module, "assert_valid_prover", new_callable=AsyncMock, return_value=None
    )

    result = await test_module.accept_proof_request(
        body=presentation, auth=mock_tenant_auth
    )

    assert result is presentation_exchange_record
    VerifierV2.accept_proof_request.assert_called_once()


@pytest.mark.anyio
async def test_accept_proof_request_v2_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        VerifierV2, "accept_proof_request", side_effect=CloudApiException("ERROR")
    )
    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v2-1234",
        anoncreds_presentation_spec=anoncreds_pres_spec,
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        test_module,
        "assert_valid_prover",
        new_callable=AsyncMock,
        return_value=None,
    )

    with pytest.raises(CloudApiException, match="500: ERROR") as exc:
        await test_module.accept_proof_request(body=presentation, auth=mock_tenant_auth)
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_accept_proof_request_v2_no_result(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(VerifierV2, "accept_proof_request", return_value=None)
    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v2-1234",
        anoncreds_presentation_spec=anoncreds_pres_spec,
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        test_module,
        "assert_valid_prover",
        new_callable=AsyncMock,
        return_value=None,
    )

    result = await test_module.accept_proof_request(
        body=presentation,
        auth=mock_tenant_auth,
    )

    assert result is None
    VerifierV2.accept_proof_request.assert_called_once()


@pytest.mark.anyio
async def test_accept_proof_request_v2_no_connection(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    presentation_exchange_record_no_conn = presentation_exchange_record.model_copy()
    presentation_exchange_record_no_conn.connection_id = None

    mocker.patch.object(
        VerifierV2,
        "accept_proof_request",
        return_value=presentation_exchange_record_no_conn,
    )
    mocker.patch.object(
        VerifierV2,
        "get_proof_record",
        return_value=presentation_exchange_record_no_conn,
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v2-1234", anoncreds_presentation_spec=anoncreds_pres_spec
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        test_module, "assert_valid_prover", new_callable=AsyncMock, return_value=None
    )

    result = await test_module.accept_proof_request(
        body=presentation,
        auth=mock_tenant_auth,
    )

    assert result is presentation_exchange_record_no_conn
    VerifierV2.accept_proof_request.assert_called_once()


@pytest.mark.anyio
async def test_reject_proof_request(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    proof_request_v2 = test_module.RejectProofRequest(
        proof_id="v2-1234", problem_report="rejected"
    )

    mocker.patch.object(
        VerifierV2, "reject_proof_request", return_value=proof_request_v2
    )
    presentation_exchange_record.state = "request-received"

    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    result = await test_module.reject_proof_request(
        body=test_module.RejectProofRequest(
            proof_id="v2-1234", problem_report="rejected"
        ),
        auth=mock_tenant_auth,
    )

    assert result is None
    VerifierV2.reject_proof_request.assert_called_once_with(
        controller=mock_agent_controller, reject_proof_request=proof_request_v2
    )
    VerifierV2.get_proof_record.assert_called_once_with(
        controller=mock_agent_controller, proof_id=proof_request_v2.proof_id
    )


@pytest.mark.anyio
async def test_reject_proof_request_bad_state(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    proof_request_v2 = test_module.RejectProofRequest(
        proof_id="v2-1234", problem_report="rejected"
    )

    presentation_exchange_record.state = "done"
    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    with pytest.raises(
        CloudApiException,
        match=(
            "400: Proof record must be in state `request-received` to reject; "
            "record has state: `done`."
        ),
    ):
        await test_module.reject_proof_request(
            body=test_module.RejectProofRequest(
                proof_id="v2-1234", problem_report="rejected"
            ),
            auth=mock_tenant_auth,
        )

    VerifierV2.get_proof_record.assert_called_once_with(
        controller=mock_agent_controller, proof_id=proof_request_v2.proof_id
    )


@pytest.mark.anyio
async def test_delete_proof(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(VerifierV2, "delete_proof", return_value=None)

    result = await test_module.delete_proof(proof_id="v2-1234", auth=mock_tenant_auth)

    assert result is None
    VerifierV2.delete_proof.assert_called_once_with(
        controller=mock_agent_controller, proof_id="v2-1234"
    )


@pytest.mark.anyio
async def test_delete_proof_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2, "delete_proof", side_effect=CloudApiException("ERROR")
    )

    with pytest.raises(CloudApiException, match="500: ERROR") as exc:
        await test_module.delete_proof(proof_id="v2-1234", auth=mock_tenant_auth)

    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_get_proof_record(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2, "get_proof_record", return_value=presentation_exchange_record
    )

    result = await test_module.get_proof_record(
        proof_id="v2-abcd", auth=mock_tenant_auth
    )

    assert result == presentation_exchange_record
    VerifierV2.get_proof_record.assert_called_once_with(
        controller=mock_agent_controller, proof_id="v2-abcd"
    )


@pytest.mark.anyio
async def test_get_proof_record_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2, "get_proof_record", side_effect=CloudApiException("ERROR")
    )

    with pytest.raises(CloudApiException, match="500: ERROR") as exc:
        await test_module.get_proof_record(proof_id="v2-abcd", auth=mock_tenant_auth)

    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_get_proof_record_no_result(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(VerifierV2, "get_proof_record", return_value=None)

    result = await test_module.get_proof_record(
        proof_id="v2-abcd",
        auth=mock_tenant_auth,
    )

    assert result is None
    VerifierV2.get_proof_record.assert_called_once_with(
        controller=mock_agent_controller, proof_id="v2-abcd"
    )


@pytest.mark.anyio
async def test_get_proof_records(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2, "get_proof_records", return_value=[presentation_exchange_record]
    )

    result = await test_module.get_proof_records(
        auth=mock_tenant_auth,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    )

    assert result == [
        presentation_exchange_record,
    ]
    VerifierV2.get_proof_records.assert_called_once_with(
        controller=mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    )


@pytest.mark.anyio
async def test_get_proof_records_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2, "get_proof_records", side_effect=CloudApiException("ERROR")
    )

    with pytest.raises(CloudApiException, match="500: ERROR"):
        await test_module.get_proof_records(
            auth=mock_tenant_auth,
            limit=50,
            offset=0,
            order_by="id",
            descending=True,
            connection_id=None,
            role=None,
            state=None,
            thread_id=None,
        )


@pytest.mark.anyio
async def test_get_proof_records_no_result(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(VerifierV2, "get_proof_records", return_value=None)

    result = await test_module.get_proof_records(
        auth=mock_tenant_auth,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    )

    assert result is None
    VerifierV2.get_proof_records.assert_called_once_with(
        controller=mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    )


@pytest.mark.anyio
async def test_get_credentials_by_proof_id(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )
    indy_cred_precis = [
        IndyCredPrecis(
            cred_info=IndyCredInfo(
                cred_def_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
                referent="abcde",
                attrs={"attr1": "value1"},
            ),
        )
    ]
    returned_cred_precis = [
        CredPrecis(
            cred_info=CredInfo(
                cred_def_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
                credential_id="abcde",
                referent="abcde",
                attrs={"attr1": "value1"},
            ),
            interval=None,
            presentation_referents=None,
        )
    ]

    # Get Indy models from acapy
    mocker.patch(
        "app.services.verifier.acapy_verifier_v2.handle_acapy_call",
        return_value=indy_cred_precis,
    )

    result = await test_module.get_credentials_by_proof_id(
        proof_id="v2-abcd",
        auth=mock_tenant_auth,
        referent=None,
        limit=100,
        offset=0,
    )

    # Assert result is converted to CredPrecis
    assert result == returned_cred_precis

    # Assert "referent" is excluded from serialized model
    assert "referent" not in result[0].cred_info.model_dump()


@pytest.mark.anyio
async def test_get_credentials_by_proof_id_exception(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mocker.patch.object(
        VerifierV2,
        "get_credentials_by_proof_id",
        side_effect=CloudApiException("ERROR"),
    )

    with pytest.raises(CloudApiException, match="500: ERROR"):
        await test_module.get_credentials_by_proof_id(
            proof_id="v2-abcd",
            auth=mock_tenant_auth,
            referent=None,
            limit=100,
            offset=0,
        )


@pytest.mark.anyio
async def test_get_credentials_by_proof_id_bad_limit():
    client = TestClient(app)

    def override_auth():
        return "mocked_auth"

    app.dependency_overrides[acapy_auth_from_header] = override_auth
    try:
        response = client.get(
            "/v1/verifier/proofs/v2-abcd/credentials",
            params={"limit": 10001, "offset": 0},
            headers={"x-api-key": "mocked_auth"},
        )
        assert response.status_code == 422
        assert response.json() == {
            "detail": [
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 10000",
                    "input": "10001",
                    "ctx": {"le": 10000},
                }
            ]
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_credentials_by_proof_id_with_limit_offset():
    mock_aries_controller = AsyncMock()

    with patch("app.routes.verifier.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credentials_by_proof_id(
            proof_id="v2-abcd",
            auth="mocked_auth",
            referent=None,
            limit=2,
            offset=1,
        )

        present_proof_v2_0 = mock_aries_controller.present_proof_v2_0
        present_proof_v2_0.get_matching_credentials.assert_called_once_with(
            pres_ex_id="abcd",
            referent=None,
            limit=2,
            offset=1,
        )
