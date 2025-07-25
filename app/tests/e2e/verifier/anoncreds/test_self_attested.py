import pytest
from aries_cloudcontroller import AnonCredsPresSpec

from app.routes.verifier import AcceptProofRequest, router
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange
from shared.models.presentation_exchange import PresentationExchange

VERIFIER_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_self_attested_attributes_anoncreds(
    acme_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
    alice_member_client: RichAsyncClient,
    issue_anoncreds_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
):
    request_body = {
        "anoncreds_proof_request": {
            "requested_attributes": {
                "name_attribute": {
                    "name": "name",
                },
                "self_attested_cell_nr": {
                    "name": "my_cell_nr",
                },
            },
            "requested_predicates": {},
        },
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "save_exchange_record": True,
    }

    send_proof_response = await send_proof_request(acme_client, request_body)

    thread_id = send_proof_response["thread_id"]
    acme_proof_id = send_proof_response["proof_id"]

    alice_event = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        filter_map={"thread_id": thread_id},
        state="request-received",
    )

    alice_proof_id = alice_event["proof_id"]

    requested_credentials = await alice_member_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
    )

    credential_id = requested_credentials.json()[0]["cred_info"]["credential_id"]

    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        anoncreds_presentation_spec=AnonCredsPresSpec(
            requested_attributes={
                "name_attribute": {
                    "cred_id": credential_id,
                    "revealed": True,
                }
            },
            requested_predicates={},
            self_attested_attributes={
                "self_attested_cell_nr": "1234567890",
            },
        ),
    )

    response = await alice_member_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json=proof_accept.model_dump(),
    )

    result = response.json()
    pres_exchange_result = PresentationExchange(**result)

    assert isinstance(pres_exchange_result, PresentationExchange)

    acme_proof_event = await check_webhook_state(
        client=acme_client,
        topic="proofs",
        state="done",
        filter_map={"thread_id": thread_id},
    )

    assert acme_proof_event["verified"] is True

    proof_response = await acme_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}"
    )
    proof = proof_response.json()

    assert "presentation" in proof, f"Proof should have presentation: {proof}"
    presentation = proof["presentation"]

    assert "requested_proof" in presentation, (
        f"Presentation should have requested_proof: {presentation}"
    )
    req = presentation["requested_proof"]

    assert "self_attested_attrs" in req, (
        f"Requested_proof should have self_attested_attrs: {req}"
    )

    assert req["self_attested_attrs"]["self_attested_cell_nr"] == "1234567890", (
        f"self_attested_attrs should have expected cell nr: {req}"
    )
