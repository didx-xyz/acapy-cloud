from typing import List

import pytest

from app.routes.verifier import router
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.regression_testing import TestMode
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

VERIFIER_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Temporarily skip; existing tests on dev don't clean up old records yet",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_limit_and_offset(
    issue_alice_anoncreds: List[CredentialExchange],  # pylint: disable=unused-argument
    acme_and_alice_connection: AcmeAliceConnect,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "anoncreds_proof_request": {
            "name": "Proof Request",
            "version": "1.0.0",
            "requested_attributes": {
                "0_speed_uuid": {
                    "name": "speed",
                },
                "0_name_uuid": {
                    "name": "name",
                },
            },
            "requested_predicates": {},
        },
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    acme_proof_id = send_proof_response["proof_id"]
    thread_id = send_proof_response["thread_id"]

    alice_payload = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    alice_proof_id = alice_payload["proof_id"]

    try:
        for limit, offset, expected_length in [
            [1, 0, 1],
            [3, 0, 3],
            [4, 0, 3],
            [1, 0, 1],
            [1, 1, 1],
            [1, 3, 0],
        ]:
            requested_credentials = (
                await alice_member_client.get(
                    f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials",
                    params={"limit": limit, "offset": offset},
                )
            ).json()

            assert len(requested_credentials) == expected_length

    finally:
        await alice_member_client.delete(
            f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}"
        )
        await acme_client.delete(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}")
