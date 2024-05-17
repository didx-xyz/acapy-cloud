from unittest.mock import AsyncMock, Mock, patch

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    ConnRecord,
    IndyCredInfo,
    IndyPresSpec,
    IndyRequestedCredsRequestedAttr,
    IndyRequestedCredsRequestedPred,
)
from assertpy import assert_that
from httpx import Response
from mockito import mock, when

from app.exceptions import CloudApiException, CloudApiValueError
from app.routes.verifier import AcceptProofRequest, SendProofRequest
from app.services.verifier.acapy_verifier import Verifier
from app.tests.services.verifier.utils import indy_pres_spec, indy_proof_request
from app.tests.util.mock import to_async
from app.util.acapy_verifier_utils import (
    VerifierFacade,
    are_valid_schemas,
    assert_valid_prover,
    assert_valid_verifier,
    ed25519_verkey_to_did_key,
    get_actor,
    get_schema_ids,
    get_verifier_by_version,
    is_verifier,
)
from shared.models.presentation_exchange import PresentationExchange
from shared.models.trustregistry import Actor

sample_actor = Actor(
    id="abcde",
    name="Flint",
    roles=["verifier"],
    did="did:sov:abcde",
    didcomm_invitation=None,
)

pres_exchange = PresentationExchange(
    connection_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    created_at="2021-09-15 13:49:47Z",
    proof_id="v1-abcd",
    presentation=None,
    presentation_request=indy_proof_request,
    role="prover",
    state="proposal-sent",
    protocol_version="v1",
    updated_at=None,
    verified="false",
)


def test_get_verifier_by_version_v1():
    assert get_verifier_by_version("v1") is VerifierFacade.v1.value


def test_get_verifier_by_version_v2():
    assert get_verifier_by_version("v2") is VerifierFacade.v2.value


def test_get_verifier_by_version_exception():
    other = "v0"
    with pytest.raises(
        CloudApiValueError,
        match=f"Unknown protocol version: `{other}`. Expecting `v1` or `v2`",
    ):
        get_verifier_by_version(other)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.schemas"], indirect=True
)
async def test_are_valid_schemas(mock_async_client: Mock):
    # schemas are valid
    schemas = [
        {
            "did": "9L2b2nqUFmY1rVMWwVVZ9y",
            "name": "test_schema",
            "version": "100.72.97",
            "id": "9L2b2nqUFmY1rVMWwVVZ9y:2:test_schema:100.72.97",
        },
        {
            "did": "9L2b2nqUFmY1rVMWwVVZ9y",
            "name": "test_schema_alt",
            "version": "53.86.35",
            "id": "9L2b2nqUFmY1rVMWwVVZ9y:2:test_schema_alt:53.86.35",
        },
    ]
    schema_ids = [schema["id"] for schema in schemas]

    mock_async_client.get = AsyncMock(return_value=Response(200, json=schemas))

    assert await are_valid_schemas(schema_ids=schema_ids) is True

    # has invalid schema
    assert (
        await are_valid_schemas(schema_ids=["SomeRandomDid:2:test_schema:0.3"]) is False
    )


@pytest.mark.anyio
async def test_get_schema_ids(mock_agent_controller: AcaPyClient):
    first_cred_record = IndyCredInfo(
        schema_id="NR6Y28AiZ893utPSfoQRrz:2:test_schema:0.3"
    )
    second_cred_record = IndyCredInfo(
        schema_id="NR6Y28AiZ893utPSfoQRrz:2:another_schema:0.3"
    )

    presentation = IndyPresSpec(
        self_attested_attributes={},
        requested_attributes={
            "group_name": IndyRequestedCredsRequestedAttr(
                revealed=False, cred_id="first-unrevealed-cred-id"
            ),
            "another_group_name": IndyRequestedCredsRequestedAttr(
                revealed=True, cred_id="first-revealed-cred-id"
            ),
        },
        requested_predicates={
            "pred_group_name": IndyRequestedCredsRequestedPred(
                cred_id="first-revealed-pred-cred-id"
            )
        },
    )

    with when(mock_agent_controller.credentials).get_record(
        credential_id="first-revealed-cred-id"
    ).thenReturn(to_async(first_cred_record)), when(
        mock_agent_controller.credentials
    ).get_record(
        credential_id="first-revealed-pred-cred-id"
    ).thenReturn(
        to_async(second_cred_record)
    ):
        got_schema_ids = await get_schema_ids(
            aries_controller=mock_agent_controller, presentation=presentation
        )

        assert_that(got_schema_ids).contains_only(
            "NR6Y28AiZ893utPSfoQRrz:2:test_schema:0.3",
            "NR6Y28AiZ893utPSfoQRrz:2:another_schema:0.3",
        )


@pytest.mark.anyio
async def test_ed25519_verkey_to_did_key():
    got_key = ed25519_verkey_to_did_key(
        key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV"
    )
    assert got_key == "did:key:z6MkvVT4kkAmhTb9srDHScsL1q7pVKt9cpUJUah2pKuYh4As"


@pytest.mark.anyio
async def test_is_verifier():
    # False
    actor = sample_actor.model_copy(update={"roles": ["issuer"]})
    assert is_verifier(actor=actor) is False

    # True
    actor = sample_actor.model_copy(update={"roles": ["issuer", "verifier"]})
    assert is_verifier(actor=actor) is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mock_async_client", ["app.services.trust_registry.actors"], indirect=True
)
async def test_get_actor(mock_async_client: Mock):
    # gets actor
    mock_async_client.get = AsyncMock(
        return_value=Response(200, json=sample_actor.model_dump())
    )

    assert await get_actor(did=sample_actor.did) == sample_actor

    # no actor
    mock_async_client.get = AsyncMock(return_value=Response(404, json={}))

    with pytest.raises(
        CloudApiException, match=f"404: No verifier with DID `{sample_actor.did}`"
    ):
        await get_actor(did=sample_actor.did)


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_invitation_key(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id,
        invitation_key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV",
    )

    presentation = IndyPresSpec(
        self_attested_attributes={},
        requested_attributes={
            "group_name": IndyRequestedCredsRequestedAttr(
                revealed=False, cred_id="first-unrevealed-cred-id"
            ),
            "another_group_name": IndyRequestedCredsRequestedAttr(
                revealed=True, cred_id="first-revealed-cred-id"
            ),
        },
        requested_predicates={
            "pred_group_name": IndyRequestedCredsRequestedPred(
                cred_id="first-revealed-pred-cred-id"
            )
        },
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    with patch(
        "app.util.acapy_verifier_utils.get_actor", return_value=sample_actor
    ), patch(
        "app.util.acapy_verifier_utils.get_schema_ids",
        return_value=["did:schema:123"],
    ), patch(
        "app.util.acapy_verifier_utils.are_valid_schemas",
        return_value=True,
    ):
        # Should not throw
        await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=presentation,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_public_did(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id, their_public_did="did:sov:123"
    )

    presentation = IndyPresSpec(
        self_attested_attributes={},
        requested_attributes={
            "group_name": IndyRequestedCredsRequestedAttr(
                revealed=False, cred_id="first-unrevealed-cred-id"
            ),
            "another_group_name": IndyRequestedCredsRequestedAttr(
                revealed=True, cred_id="first-revealed-cred-id"
            ),
        },
        requested_predicates={
            "pred_group_name": IndyRequestedCredsRequestedPred(
                cred_id="first-revealed-pred-cred-id"
            )
        },
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    with patch(
        "app.util.acapy_verifier_utils.get_actor", return_value=sample_actor
    ), patch(
        "app.util.acapy_verifier_utils.get_schema_ids",
        return_value=["did:schema:123"],
    ), patch(
        "app.util.acapy_verifier_utils.are_valid_schemas",
        return_value=True,
    ):
        # Should not throw
        await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=presentation,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_no_public_did_no_invitation_key(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(connection_id=test_pres_exchange.connection_id)

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    with pytest.raises(
        CloudApiException, match="Could not determine did of the verifier"
    ):
        await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=indy_pres_spec,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_actor_invalid_role(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    actor = sample_actor.model_copy(update={"roles": ["issuer"]})

    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id, their_public_did="xxx"
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.get_actor",
        return_value=actor,
    ):
        with pytest.raises(
            CloudApiException, match="Actor is missing required role 'verifier'"
        ):
            await assert_valid_prover(
                aries_controller=mock_agent_controller,
                presentation=AcceptProofRequest(
                    proof_id=test_pres_exchange.proof_id,
                    indy_presentation_spec=indy_pres_spec,
                ),
                verifier=verifier,
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_could_not_fetch_actor_recover_label(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id,
        their_public_did="xxx",
        their_label="some_label",
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        return_value=None,
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_name",
        return_value=sample_actor,
    ), patch(
        "app.util.acapy_verifier_utils.get_schema_ids",
        return_value=["did:schema:456"],
    ), patch(
        "app.util.acapy_verifier_utils.are_valid_schemas",
        return_value=True,
    ):
        await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=indy_pres_spec,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_could_not_fetch_actor_exc(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id,
        their_public_did="xxx",
        their_label="some_label",
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.get_actor",
        side_effect=CloudApiException("Error", 500),
    ):
        with pytest.raises(
            CloudApiException,
            match="An error occurred while asserting valid verifier. Please try again.",
        ):
            await assert_valid_prover(
                aries_controller=mock_agent_controller,
                presentation=AcceptProofRequest(
                    proof_id=test_pres_exchange.proof_id,
                    indy_presentation_spec=indy_pres_spec,
                ),
                verifier=verifier,
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_could_not_fetch_actor_exc2(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={"protocol_version": protocol_version}
    )
    conn_record = ConnRecord(
        connection_id=test_pres_exchange.connection_id,
        their_public_did="xxx",
        their_label="some_label",
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=test_pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.get_actor",
        side_effect=Exception("Error."),
    ):
        with pytest.raises(Exception, match="Error."):
            await assert_valid_prover(
                aries_controller=mock_agent_controller,
                presentation=AcceptProofRequest(
                    proof_id=test_pres_exchange.proof_id,
                    indy_presentation_spec=indy_pres_spec,
                ),
                verifier=verifier,
            )


@pytest.mark.anyio
async def test_assert_valid_prover_x_invalid_schemas(
    mock_agent_controller: AcaPyClient,
):
    conn_record = ConnRecord(
        connection_id=pres_exchange.connection_id, their_public_did="xxx"
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=pres_exchange.proof_id
    ).thenReturn(to_async(pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    with patch(
        "app.util.acapy_verifier_utils.get_actor", return_value=sample_actor
    ), patch(
        "app.util.acapy_verifier_utils.get_schema_ids",
        return_value=["did:schema:456"],
    ), patch(
        "app.util.acapy_verifier_utils.are_valid_schemas",
        return_value=False,
    ):
        with pytest.raises(
            CloudApiException,
            match="Presentation is using schemas not registered in trust registry",
        ):
            await assert_valid_prover(
                aries_controller=mock_agent_controller,
                presentation=AcceptProofRequest(
                    proof_id=pres_exchange.proof_id,
                    indy_presentation_spec=indy_pres_spec,
                ),
                verifier=verifier,
            )


@pytest.mark.anyio
async def test_assert_valid_prover_x_no_schemas(
    mock_agent_controller: AcaPyClient,
):
    conn_record = ConnRecord(
        connection_id=pres_exchange.connection_id, their_public_did="xxx"
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=pres_exchange.proof_id
    ).thenReturn(to_async(pres_exchange))
    when(mock_agent_controller.connection).get_connection(
        conn_id=pres_exchange.connection_id
    ).thenReturn(to_async(conn_record))

    with patch(
        "app.util.acapy_verifier_utils.get_actor", return_value=sample_actor
    ), patch(
        "app.util.acapy_verifier_utils.get_schema_ids",
        return_value=[],
    ):
        with pytest.raises(
            CloudApiException,
            match="Presentation is using schemas not registered in trust registry",
        ):
            await assert_valid_prover(
                aries_controller=mock_agent_controller,
                presentation=AcceptProofRequest(
                    proof_id=pres_exchange.proof_id,
                    indy_presentation_spec=indy_pres_spec,
                ),
                verifier=verifier,
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_no_connection_id(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={
            "connection_id": None,
            "protocol_version": protocol_version,
        }
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))

    with pytest.raises(
        CloudApiException, match="No connection id associated with proof request."
    ):
        assert await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=indy_pres_spec,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_prover_x_no_connection_id2(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    test_pres_exchange = pres_exchange.model_copy(
        update={
            "connection_id": "a-connection-id",
            "protocol_version": protocol_version,
        }
    )

    verifier = mock(Verifier)

    when(verifier).get_proof_record(
        controller=mock_agent_controller, proof_id=test_pres_exchange.proof_id
    ).thenReturn(to_async(test_pres_exchange))

    when(mock_agent_controller.connection).get_connection(
        conn_id="a-connection-id"
    ).thenReturn(to_async(ConnRecord(connection_id=None)))

    with pytest.raises(CloudApiException, match="Cannot proceed. No connection id."):
        assert await assert_valid_prover(
            aries_controller=mock_agent_controller,
            presentation=AcceptProofRequest(
                proof_id=test_pres_exchange.proof_id,
                indy_presentation_spec=indy_pres_spec,
            ),
            verifier=verifier,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_invitation_key(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    conn = ConnRecord(
        connection_id="a-connection-id",
        invitation_key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV",
    )

    when(mock_agent_controller.connection).get_connection(
        conn_id="a-connection-id"
    ).thenReturn(to_async(conn))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        side_effect=Exception("Error"),
    ), patch("app.util.acapy_verifier_utils.get_actor", return_value=sample_actor):
        await assert_valid_verifier(
            aries_controller=mock_agent_controller,
            proof_request=SendProofRequest(
                protocol_version=protocol_version,
                connection_id="a-connection-id",
                indy_proof_request=indy_proof_request,
            ),
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_public_did(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # valid
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch("app.util.acapy_verifier_utils.get_actor", return_value=sample_actor):
        await assert_valid_verifier(
            aries_controller=mock_agent_controller,
            proof_request=SendProofRequest(
                protocol_version=protocol_version,
                connection_id="abcde",
                indy_proof_request=indy_proof_request,
            ),
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_no_public_did_no_invitation_key(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    conn = ConnRecord(
        connection_id="a-connection-id",
    )

    when(mock_agent_controller.connection).get_connection(
        conn_id="a-connection-id"
    ).thenReturn(to_async(conn))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        side_effect=Exception("Error"),
    ), patch("app.util.acapy_verifier_utils.get_actor", return_value=sample_actor):
        with pytest.raises(CloudApiException, match="Connection has no invitation key"):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_not_verifier(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    actor = sample_actor.model_copy(update={"roles": ["issuer"]})

    conn = ConnRecord(
        connection_id="a-connection-id",
        invitation_key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV",
    )

    when(mock_agent_controller.connection).get_connection(
        conn_id="a-connection-id"
    ).thenReturn(to_async(conn))

    # valid
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        side_effect=Exception("Error"),
    ), patch("app.util.acapy_verifier_utils.get_actor", return_value=actor):
        with pytest.raises(
            CloudApiException,
            match="Flint is not a valid verifier in the trust registry.",
        ):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_could_not_fetch_actor_recover_label(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # valid with recovery from actor not found, using label
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        return_value=None,
    ), patch(
        "app.util.acapy_verifier_utils.get_wallet_label_from_controller",
        return_value="some_label",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_name",
        return_value=sample_actor,
    ):
        await assert_valid_verifier(
            aries_controller=mock_agent_controller,
            proof_request=SendProofRequest(
                protocol_version=protocol_version,
                connection_id="a-connection-id",
                indy_proof_request=indy_proof_request,
            ),
        )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_could_not_fetch_actor_exc(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # failure to attempt recovery by reading wallet_label: No actor
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        return_value=None,
    ), patch(
        "app.util.acapy_verifier_utils.get_wallet_label_from_controller",
        return_value=None,
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_name",
        return_value=None,
    ):
        with pytest.raises(
            CloudApiException,
            match="No verifier with name",
        ):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_could_not_fetch_actor_exc2(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # failure to attempt recovery by reading wallet_label
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        return_value=None,
    ), patch(
        "app.util.acapy_verifier_utils.get_wallet_label_from_controller",
        side_effect=KeyError("Oops"),
    ):
        with pytest.raises(
            CloudApiException,
            match="No verifier with DID",
        ):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_could_not_fetch_actor_exc3(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # failure to attempt recovery by reading wallet_label
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        side_effect=CloudApiException("Error.", 500),
    ):
        with pytest.raises(
            CloudApiException,
            match="An error occurred while asserting valid verifier. Please try again.",
        ):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
async def test_assert_valid_verifier_x_could_not_fetch_actor_exc4(
    mock_agent_controller: AcaPyClient, protocol_version: str
):
    # failure to attempt recovery by reading wallet_label
    with patch(
        "app.util.acapy_verifier_utils.assert_public_did",
        return_value="did:sov:something",
    ), patch(
        "app.util.acapy_verifier_utils.fetch_actor_by_did",
        side_effect=Exception("Error."),
    ):
        with pytest.raises(Exception, match="Error."):
            await assert_valid_verifier(
                aries_controller=mock_agent_controller,
                proof_request=SendProofRequest(
                    protocol_version=protocol_version,
                    connection_id="a-connection-id",
                    indy_proof_request=indy_proof_request,
                ),
            )
