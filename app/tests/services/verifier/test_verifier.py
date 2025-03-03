from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import AcaPyClient, ConnRecord, IndyCredInfo, IndyCredPrecis
from fastapi.testclient import TestClient
from mockito import verify, when
from pytest_mock import MockerFixture

from app.models.verifier import CredInfo, CredPrecis
import app.routes.verifier as test_module
from app.dependencies.auth import AcaPyAuth
from app.exceptions.cloudapi_exception import CloudApiException
from app.main import app
from app.routes.verifier import acapy_auth_from_header, get_credentials_by_proof_id
from app.services.verifier.acapy_verifier_v2 import VerifierV2
from app.tests.services.verifier.utils import indy_pres_spec, sample_indy_proof_request
from app.tests.util.mock import to_async
from app.util import acapy_verifier_utils
from shared.models.presentation_exchange import PresentationExchange
from shared.models.trustregistry import Actor
from shared.util.mock_agent_controller import MockContextManagedController

presentation_exchange_record_2 = PresentationExchange(
    connection_id="abcde",
    created_at="2021-11-22 11:37:45.179595Z",
    updated_at="2021-11-22 11:37:45.179595Z",
    proof_id="abcde",
    presentation={},
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
    # V2
    when(VerifierV2).send_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_2)
    )

    when(mock_agent_controller.connection).get_connection(conn_id="abcde").thenReturn(
        to_async(conn_record)
    )

    when(mock_agent_controller.wallet).get_public_did().thenRaise(
        CloudApiException("No did")
    )

    when(acapy_verifier_utils).get_actor(
        did="did:key:z6MkvVT4kkAmhTb9srDHScsL1q7pVKt9cpUJUah2pKuYh4As"
    ).thenReturn(to_async(actor))

    send_proof_request = test_module.SendProofRequest(
        connection_id="abcde",
        indy_proof_request=sample_indy_proof_request(),
    )

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    result = await test_module.send_proof_request(
        body=send_proof_request,
        auth=mock_tenant_auth,
    )

    assert result is presentation_exchange_record_2
    verify(VerifierV2).send_proof_request(
        controller=mock_agent_controller, send_proof_request=send_proof_request
    )


@pytest.mark.anyio
async def test_create_proof_request(mock_tenant_auth: AcaPyAuth):
    when(VerifierV2).create_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_2)
    )
    result = await test_module.create_proof_request(
        body=test_module.CreateProofRequest(
            indy_proof_request=sample_indy_proof_request(),
            connection_id="abcde",
        ),
        auth=mock_tenant_auth,
    )
    assert result is presentation_exchange_record_2


@pytest.mark.anyio
async def test_accept_proof_request_v2(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    # V2
    when(VerifierV2).accept_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_2)
    )
    when(VerifierV2).get_proof_record(...).thenReturn(
        to_async(presentation_exchange_record_2)
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v2-1234", indy_presentation_spec=indy_pres_spec
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

    assert result is presentation_exchange_record_2
    verify(VerifierV2).accept_proof_request(...)


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

    when(VerifierV2).reject_proof_request(
        controller=mock_agent_controller, reject_proof_request=proof_request_v2
    ).thenReturn(to_async(None))
    presentation_exchange_record_2.state = "request-received"
    when(VerifierV2).get_proof_record(
        controller=mock_agent_controller, proof_id=proof_request_v2.proof_id
    ).thenReturn(to_async(presentation_exchange_record_2))

    result = await test_module.reject_proof_request(
        body=test_module.RejectProofRequest(
            proof_id="v2-1234", problem_report="rejected"
        ),
        auth=mock_tenant_auth,
    )

    assert result is None
    verify(VerifierV2).reject_proof_request(
        controller=mock_agent_controller, reject_proof_request=proof_request_v2
    )
    verify(VerifierV2).get_proof_record(
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

    when(VerifierV2).delete_proof(
        controller=mock_agent_controller, proof_id="v2-1234"
    ).thenReturn(to_async())

    result = await test_module.delete_proof(proof_id="v2-1234", auth=mock_tenant_auth)

    assert result is None
    verify(VerifierV2).delete_proof(
        controller=mock_agent_controller, proof_id="v2-1234"
    )


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

    # V2
    when(VerifierV2).get_proof_record(
        controller=mock_agent_controller, proof_id="v2-abcd"
    ).thenReturn(to_async(presentation_exchange_record_2))

    result = await test_module.get_proof_record(
        proof_id="v2-abcd",
        auth=mock_tenant_auth,
    )

    assert result == presentation_exchange_record_2
    verify(VerifierV2).get_proof_record(
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
    with when(VerifierV2).get_proof_records(
        controller=mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    ).thenReturn(to_async([presentation_exchange_record_2])):
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
            presentation_exchange_record_2,
        ]
        verify(VerifierV2).get_proof_records(
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
    cred_precis = [IndyCredPrecis(
        cred_info=IndyCredInfo(cred_def_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag", referent="abcde", attrs={"attr1": "value1"}),
    )]
    returned_cred_precis = [
        CredPrecis(
            cred_info=CredInfo(
                **cred.cred_info.model_dump(),
                credential_id=cred.cred_info.referent
            ),
            interval=cred.interval,
            presentation_referents=cred.presentation_referents,
        )
        for cred in cred_precis ]

    # V2
    when(VerifierV2).get_credentials_by_proof_id(
        controller=mock_agent_controller,
        proof_id="v2-abcd",
        referent=None,
        limit=100,
        offset=0,
    ).thenReturn(to_async(cred_precis))

    result = await test_module.get_credentials_by_proof_id(
        proof_id="v2-abcd",
        auth=mock_tenant_auth,
        referent=None,
        limit=100,
        offset=0,
    )

    assert result == returned_cred_precis
    verify(VerifierV2).get_credentials_by_proof_id(
        controller=mock_agent_controller,
        proof_id="v2-abcd",
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

        mock_aries_controller.present_proof_v2_0.get_matching_credentials.assert_called_once_with(
            pres_ex_id="abcd",
            referent=None,
            limit=2,
            offset=1,
        )
