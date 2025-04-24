import pytest
from aries_cloudcontroller import (
    AnonCredsPresSpec,
    AnonCredsRequestedCredsRequestedAttr,
    AttachmentDef,
)

from app.routes.connections import router as connections_router
from app.routes.oob import AcceptOobInvitation, CreateOobInvitation
from app.routes.oob import router as oob_router
from app.routes.verifier import AcceptProofRequest, CreateProofRequest
from app.routes.verifier import router as verifier_router
from app.services.trust_registry.actors import fetch_actor_by_id
from app.tests.services.verifier.utils import sample_anoncreds_proof_request
from app.tests.util.regression_testing import TestMode
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import check_webhook_state, get_wallet_id_from_async_client
from app.util.string import base64_to_json
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group_3")

OOB_BASE_PATH = oob_router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix
CONNECTIONS_BASE_PATH = connections_router.prefix


@pytest.mark.anyio
async def test_accept_proof_request_oob(
    issue_anoncreds_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    alice_member_client: RichAsyncClient,
    bob_member_client: RichAsyncClient,
):
    # Create the proof request against aca-py
    create_proof_request = CreateProofRequest(
        type="anoncreds",
        anoncreds_proof_request=sample_anoncreds_proof_request(),
        comment="some comment",
    )
    create_proof_response = await bob_member_client.post(
        VERIFIER_BASE_PATH + "/create-request",
        json=create_proof_request.model_dump(by_alias=True),
    )
    bob_exchange = create_proof_response.json()
    thread_id = bob_exchange["thread_id"]

    create_oob_invitation_request = CreateOobInvitation(
        create_connection=False,
        use_public_did=False,
        attachments=[AttachmentDef(id=bob_exchange["proof_id"], type="present-proof")],
    )

    invitation_response = await bob_member_client.post(
        f"{OOB_BASE_PATH}/create-invitation",
        json=create_oob_invitation_request.model_dump(),
    )
    assert invitation_response.status_code == 200
    invitation = (invitation_response.json())["invitation"]

    accept_oob_invitation_request = AcceptOobInvitation(invitation=invitation)
    await alice_member_client.post(
        f"{OOB_BASE_PATH}/accept-invitation",
        json=accept_oob_invitation_request.model_dump(by_alias=True),
    )

    alice_request_received = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    alice_proof_id = alice_request_received["proof_id"]
    assert alice_proof_id

    requested_credentials = await alice_member_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
    )

    referent = requested_credentials.json()[0]["cred_info"]["referent"]
    assert referent

    anoncreds_request_attrs = AnonCredsRequestedCredsRequestedAttr(
        cred_id=referent, revealed=True
    )
    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        anoncreds_presentation_spec=AnonCredsPresSpec(
            requested_attributes={"0_speed_uuid": anoncreds_request_attrs},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    accept_response = await alice_member_client.post(
        VERIFIER_BASE_PATH + "/accept-request",
        json=proof_accept.model_dump(),
    )
    assert accept_response.status_code == 200

    assert await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="presentation-sent",
        filter_map={
            "proof_id": alice_proof_id,
        },
    )

    bob_presentation_received = await check_webhook_state(
        client=bob_member_client,
        topic="proofs",
        state="done",
        filter_map={
            "thread_id": thread_id,
        },
    )
    assert bob_presentation_received["role"] == "verifier"


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Verifier trust registry OOB connection already tested in test_verifier",
)
async def test_accept_proof_request_verifier_oob_connection(
    anoncreds_credential_definition_id: str,
    issue_anoncreds_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    # Create connection between holder and verifier
    # We need to use the multi-use didcomm invitation from the trust registry
    acme_wallet_id = get_wallet_id_from_async_client(acme_client)
    verifier_actor = await fetch_actor_by_id(acme_wallet_id)

    # Get Alice's wallet_label from RichAsyncClient instance, striping prefix and suffix added by fixtures
    # Example of RichAsyncClient name format: "Tenant alice_VCPSU - HTTP"
    their_label = alice_member_client.name[7:-7]

    assert verifier_actor
    assert verifier_actor.didcomm_invitation

    invitation_json = base64_to_json(
        verifier_actor.didcomm_invitation.split("?oob=")[1]
    )
    invitation_response = (
        await alice_member_client.post(
            OOB_BASE_PATH + "/accept-invitation",
            json={"invitation": invitation_json},
        )
    ).json()

    payload = await check_webhook_state(
        client=acme_client,
        topic="connections",
        state="completed",
        filter_map={"their_label": their_label},
    )
    holder_verifier_connection_id = invitation_response["connection_id"]
    verifier_holder_connection_id = payload["connection_id"]

    try:
        # Present proof from holder to verifier
        request_body = {
            "connection_id": verifier_holder_connection_id,
            "type": "anoncreds",
            "anoncreds_proof_request": {
                "name": "Age Check",
                "version": "1.0",
                "requested_attributes": {
                    "name": {
                        "name": "name",
                        "restrictions": [
                            {"cred_def_id": anoncreds_credential_definition_id}
                        ],
                    }
                },
                "requested_predicates": {
                    "age_over_21": {
                        "name": "age",
                        "p_type": ">=",
                        "p_value": 21,
                        "restrictions": [
                            {"cred_def_id": anoncreds_credential_definition_id}
                        ],
                    }
                },
            },
        }
        send_proof_response = await send_proof_request(acme_client, request_body)

        payload = await check_webhook_state(
            client=alice_member_client,
            topic="proofs",
            state="request-received",
            filter_map={
                "connection_id": holder_verifier_connection_id,
            },
        )

        verifier_proof_exchange_id = send_proof_response["proof_id"]
        holder_proof_exchange_id = payload["proof_id"]

        available_credentials = (
            await alice_member_client.get(
                f"{VERIFIER_BASE_PATH}/proofs/{holder_proof_exchange_id}/credentials",
            )
        ).json()

        cred_id = available_credentials[0]["cred_info"]["referent"]

        await alice_member_client.post(
            VERIFIER_BASE_PATH + "/accept-request",
            json={
                "proof_id": holder_proof_exchange_id,
                "anoncreds_presentation_spec": {
                    "requested_attributes": {
                        "name": {
                            "cred_id": cred_id,
                            "revealed": True,
                        }
                    },
                    "requested_predicates": {"age_over_21": {"cred_id": cred_id}},
                    "self_attested_attributes": {},
                },
            },
        )

        event = await check_webhook_state(
            client=acme_client,
            topic="proofs",
            state="done",
            filter_map={
                "proof_id": verifier_proof_exchange_id,
            },
        )
        assert event["verified"]

    finally:
        # Clean up temp connection records
        await alice_member_client.delete(
            f"{CONNECTIONS_BASE_PATH}/{holder_verifier_connection_id}"
        )
        # Alice deleting record also hands up for verifier, since it uses didexchange protocol
