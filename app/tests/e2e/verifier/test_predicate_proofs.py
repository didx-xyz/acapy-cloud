import pytest
from aries_cloudcontroller import IndyPresSpec
from fastapi import HTTPException

from app.routes.verifier import AcceptProofRequest, router
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange
from shared.models.presentation_exchange import PresentationExchange

VERIFIER_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", ["v1", "v2"])
@pytest.mark.parametrize("predicate", ["<", ">", "<=", ">="])
async def test_predicate_proofs(
    protocol_version: str,
    acme_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
    alice_member_client: RichAsyncClient,
    issue_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    predicate: str,
):
    request_body = {
        "type": "indy",
        "protocol_version": protocol_version,
        "indy_proof_request": {
            "requested_attributes": {},
            "requested_predicates": {
                "over_18": {
                    "name": "age",
                    "p_type": predicate,
                    "p_value": 18,
                }
            },
        },
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "save_exchange_record": True,
    }

    send_proof_response = await send_proof_request(acme_client, request_body)

    thread_id = send_proof_response["thread_id"]

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

    referent = requested_credentials.json()[0]["cred_info"]["referent"]

    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={},
            requested_predicates={
                "over_18": {
                    "cred_id": referent,
                }
            },
            self_attested_attributes={},
        ),
    )

    if predicate in [">", ">="]:
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
            look_back=5,
        )
        assert acme_proof_event["verified"] is True

    else:
        with pytest.raises(HTTPException) as exc:
            await alice_member_client.post(
                f"{VERIFIER_BASE_PATH}/accept-request",
                json=proof_accept.model_dump(),
            )
        assert exc.value.status_code == 400
        assert exc.value.detail.startswith(
            '{"detail":"Failed to send proof presentation: Error creating presentation. Invalid state: Predicate is not satisfied.."}'
        )
