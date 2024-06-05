from unittest.mock import AsyncMock

import pytest
from aries_cloudcontroller import AcaPyClient, ConnRecord, IndyCredInfo, IndyCredPrecis
from mockito import verify, when
from pytest_mock import MockerFixture

import app.routes.verifier as test_module
from app.dependencies.auth import AcaPyAuth
from app.exceptions.cloudapi_exception import CloudApiException
from app.services.verifier.acapy_verifier_v1 import VerifierV1
from app.services.verifier.acapy_verifier_v2 import VerifierV2
from app.tests.services.verifier.utils import indy_pres_spec, sample_indy_proof_request
from app.tests.util.mock import to_async
from app.util import acapy_verifier_utils
from shared.models.presentation_exchange import PresentationExchange
from shared.models.protocol import PresentProofProtocolVersion
from shared.models.trustregistry import Actor
from shared.util.mock_agent_controller import MockContextManagedController

presentation_exchange_record_1 = PresentationExchange(
    connection_id="abcde",
    created_at="2021-11-22 11:37:45.179595Z",
    updated_at="2021-11-22 11:37:45.179595Z",
    proof_id="abcde",
    protocol_version=PresentProofProtocolVersion.V1.value,
    presentation={},
    role="prover",
    state="presentation-sent",
    verified=False,
)

presentation_exchange_record_2 = PresentationExchange(
    connection_id="abcde",
    created_at="2021-11-22 11:37:45.179595Z",
    updated_at="2021-11-22 11:37:45.179595Z",
    proof_id="abcde",
    protocol_version=PresentProofProtocolVersion.V2.value,
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
async def test_send_proof_request_v1(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    # V1
    when(VerifierV1).send_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_1)
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
        protocol_version="v1",
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

    assert result is presentation_exchange_record_1
    verify(VerifierV1).send_proof_request(
        controller=mock_agent_controller, send_proof_request=send_proof_request
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
        protocol_version="v2",
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
    #  V1
    when(VerifierV1).create_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_1)
    )
    result = await test_module.create_proof_request(
        body=test_module.CreateProofRequest(
            protocol_version="v1",
            indy_proof_request=sample_indy_proof_request(),
            connection_id="abcde",
        ),
        auth=mock_tenant_auth,
    )
    assert result is presentation_exchange_record_1

    #  V2
    when(VerifierV2).create_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_2)
    )
    result = await test_module.create_proof_request(
        body=test_module.CreateProofRequest(
            protocol_version="v2",
            indy_proof_request=sample_indy_proof_request(),
            connection_id="abcde",
        ),
        auth=mock_tenant_auth,
    )
    assert result is presentation_exchange_record_2


@pytest.mark.anyio
async def test_accept_proof_request_v1(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    # V1
    when(VerifierV1).accept_proof_request(...).thenReturn(
        to_async(presentation_exchange_record_1)
    )
    when(VerifierV1).get_proof_record(...).thenReturn(
        to_async(presentation_exchange_record_1)
    )

    presentation = test_module.AcceptProofRequest(
        proof_id="v1-1234", indy_presentation_spec=indy_pres_spec
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

    assert result is presentation_exchange_record_1
    verify(VerifierV1).accept_proof_request(...)


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
    proof_request_v1 = test_module.RejectProofRequest(
        proof_id="v1-1234", problem_report="rejected"
    )
    # V1

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    when(VerifierV1).reject_proof_request(
        controller=mock_agent_controller, reject_proof_request=proof_request_v1
    ).thenReturn(to_async(None))
    presentation_exchange_record_1.state = "request-received"
    when(VerifierV1).get_proof_record(
        controller=mock_agent_controller, proof_id=proof_request_v1.proof_id
    ).thenReturn(to_async(presentation_exchange_record_1))

    result = await test_module.reject_proof_request(
        body=test_module.RejectProofRequest(
            proof_id="v1-1234", problem_report="rejected"
        ),
        auth=mock_tenant_auth,
    )

    assert result is None
    verify(VerifierV1).reject_proof_request(
        controller=mock_agent_controller, reject_proof_request=proof_request_v1
    )
    verify(VerifierV1).get_proof_record(
        controller=mock_agent_controller, proof_id=proof_request_v1.proof_id
    )

    proof_request_v2 = test_module.RejectProofRequest(
        proof_id="v2-1234", problem_report="rejected"
    )

    # V2
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

    # V1
    when(VerifierV1).delete_proof(
        controller=mock_agent_controller, proof_id="v1-1234"
    ).thenReturn(to_async())

    result = await test_module.delete_proof(proof_id="v1-1234", auth=mock_tenant_auth)

    assert result is None
    verify(VerifierV1).delete_proof(
        controller=mock_agent_controller, proof_id="v1-1234"
    )

    # V2
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

    # V1
    when(VerifierV1).get_proof_record(
        controller=mock_agent_controller, proof_id="v1-abcd"
    ).thenReturn(to_async(presentation_exchange_record_1))

    result = await test_module.get_proof_record(
        proof_id="v1-abcd",
        auth=mock_tenant_auth,
    )

    assert result == presentation_exchange_record_1
    verify(VerifierV1).get_proof_record(
        controller=mock_agent_controller, proof_id="v1-abcd"
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
    # V1 and V2
    with when(VerifierV1).get_proof_records(
        controller=mock_agent_controller,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    ).thenReturn(to_async([presentation_exchange_record_1])), when(
        VerifierV2
    ).get_proof_records(
        controller=mock_agent_controller,
        connection_id=None,
        role=None,
        state=None,
        thread_id=None,
    ).thenReturn(
        to_async([presentation_exchange_record_2])
    ):
        result = await test_module.get_proof_records(
            auth=mock_tenant_auth,
            connection_id=None,
            role=None,
            state=None,
            thread_id=None,
        )

        assert result == [
            presentation_exchange_record_1,
            presentation_exchange_record_2,
        ]
        verify(VerifierV1).get_proof_records(
            controller=mock_agent_controller,
            connection_id=None,
            role=None,
            state=None,
            thread_id=None,
        )
        verify(VerifierV2).get_proof_records(
            controller=mock_agent_controller,
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
    cred_precis = IndyCredPrecis(
        cred_info=IndyCredInfo(cred_def_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag")
    )
    # V1
    when(VerifierV1).get_credentials_by_proof_id(
        controller=mock_agent_controller, proof_id="v1-abcd"
    ).thenReturn(to_async([cred_precis]))

    result = await test_module.get_credentials_by_proof_id(
        proof_id="v1-abcd",
        auth=mock_tenant_auth,
    )

    assert result == [cred_precis]
    verify(VerifierV1).get_credentials_by_proof_id(
        controller=mock_agent_controller, proof_id="v1-abcd"
    )

    # V2
    when(VerifierV2).get_credentials_by_proof_id(
        controller=mock_agent_controller, proof_id="v2-abcd"
    ).thenReturn(to_async([cred_precis]))

    result = await test_module.get_credentials_by_proof_id(
        proof_id="v2-abcd",
        auth=mock_tenant_auth,
    )

    assert result == [cred_precis]
    verify(VerifierV2).get_credentials_by_proof_id(
        controller=mock_agent_controller, proof_id="v2-abcd"
    )
