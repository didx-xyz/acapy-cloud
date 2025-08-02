import asyncio
import time
from typing import Any

import pytest

from app.routes.verifier import router as verifier_router
from app.tests.util.connections import BobAliceConnect
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared.util.rich_async_client import RichAsyncClient

VERIFIER_BASE_PATH = verifier_router.prefix


async def send_proof_request(
    client: RichAsyncClient, json_body: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        VERIFIER_BASE_PATH + "/send-request",
        json=json_body,
    )
    return response.json()


async def send_proof_and_assert_verified(
    verifier_client: RichAsyncClient,
    holder_client: RichAsyncClient,
    bob_alice_connection: BobAliceConnect,
    cred_def_id: str,
    verified: bool,
):
    # Do proof request
    request_body = {
        "comment": "Test proof of revocation",
        "anoncreds_proof_request": {
            "name": "Proof of SPEED",
            "version": "1.0",
            "non_revoked": {"to": int(time.time())},
            "requested_attributes": {
                "THE_SPEED": {
                    "name": "speed",
                    "restrictions": [{"cred_def_id": cred_def_id}],
                }
            },
            "requested_predicates": {},
        },
        "save_exchange_record": True,
        "connection_id": bob_alice_connection.bob_connection_id,
    }
    send_proof_response = await send_proof_request(verifier_client, request_body)
    acme_proof_exchange_id = send_proof_response["proof_id"]

    alice_payload = await check_webhook_state(
        client=holder_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": send_proof_response["thread_id"],
        },
    )

    alice_proof_exchange_id = alice_payload["proof_id"]

    # Get referent -- retry loop because sometimes the credentials don't show up
    retry_count = 0
    max_retries = 10
    while retry_count < max_retries:
        creds = (
            await holder_client.get(
                f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_exchange_id}/credentials"
            )
        ).json()
        if creds:
            break

        retry_count += 1
        if retry_count == max_retries:
            pytest.fail(f"No credentials found for proof {alice_proof_exchange_id}")
        await asyncio.sleep(1)

    referent = creds[0]["cred_info"]["credential_id"]

    # Send proof
    await holder_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json={
            "proof_id": alice_proof_exchange_id,
            "anoncreds_presentation_spec": {
                "requested_attributes": {
                    "THE_SPEED": {"cred_id": referent, "revealed": True}
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
        },
    )

    await assert_both_webhooks_received(
        holder_client,
        verifier_client,
        "proofs",
        "done",
        alice_proof_exchange_id,
        acme_proof_exchange_id,
    )

    # Check proof
    proof = (
        await verifier_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_exchange_id}"
        )
    ).json()

    assert proof["verified"] is verified
