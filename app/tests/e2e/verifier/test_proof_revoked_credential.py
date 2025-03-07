import asyncio
import time
from typing import List

import pytest

from app.routes.issuer import router as issuer_router
from app.routes.verifier import router as verifier_router
from app.tests.fixtures.credentials import ReferentCredDef
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.regression_testing import TestMode
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = issuer_router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize(
    "revoke_alice_indy_creds_and_publish",
    ["auto_publish_true", "default"],
    indirect=True,
)
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Proving revoked credentials is currently non-deterministic",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_proof_revoked_credential(
    revoke_alice_indy_creds_and_publish: List[  # pylint: disable=unused-argument
        CredentialExchange
    ],
    indy_credential_definition_id_revocable: str,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
):
    await asyncio.sleep(14)  # moment for revocation registry to update
    # todo: remove sleep when issue resolved: https://github.com/openwallet-foundation/acapy/issues/3018

    # Do proof request
    request_body = {
        "comment": "Test proof of revocation",
        "type": "indy",
        "indy_proof_request": {
            "name": "Proof of SPEED",
            "version": "1.0",
            "non_revoked": {"to": int(time.time())},
            "requested_attributes": {
                "THE_SPEED": {
                    "name": "speed",
                    "restrictions": [
                        {"cred_def_id": indy_credential_definition_id_revocable}
                    ],
                }
            },
            "requested_predicates": {},
        },
        "save_exchange_record": True,
        "connection_id": acme_and_alice_connection.acme_connection_id,
    }
    send_proof_response = await send_proof_request(acme_client, request_body)
    acme_proof_exchange_id = send_proof_response["proof_id"]

    alice_payload = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": send_proof_response["thread_id"],
        },
    )

    alice_proof_exchange_id = alice_payload["proof_id"]

    # Get referent
    referent = (
        await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_exchange_id}/credentials"
        )
    ).json()[0]["cred_info"]["referent"]

    # Send proof
    await alice_member_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json={
            "proof_id": alice_proof_exchange_id,
            "type": "indy",
            "indy_presentation_spec": {
                "requested_attributes": {
                    "THE_SPEED": {"cred_id": referent, "revealed": True}
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
            "dif_presentation_spec": {},
        },
    )

    await assert_both_webhooks_received(
        alice_member_client,
        acme_client,
        "proofs",
        "done",
        alice_proof_exchange_id,
        acme_proof_exchange_id,
    )

    # Check proof
    proof = (
        await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_exchange_id}")
    ).json()

    assert proof["verified"] is False


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.clean_run in TestMode.fixture_params,
    reason="Run only in regression mode",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_regression_proof_revoked_credential(
    get_or_issue_regression_cred_revoked: ReferentCredDef,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
):
    await asyncio.sleep(14)  # moment for revocation registry to update
    # todo: remove sleep when issue resolved: https://github.com/openwallet-foundation/acapy/issues/3018

    referent = get_or_issue_regression_cred_revoked.referent
    credential_definition_id_revocable = (
        get_or_issue_regression_cred_revoked.cred_def_revocable
    )

    # Do proof request
    request_body = {
        "comment": "Test proof of revocation",
        "type": "indy",
        "indy_proof_request": {
            "non_revoked": {"to": int(time.time())},
            "requested_attributes": {
                "THE_SPEED": {
                    "name": "speed",
                    "restrictions": [
                        {"cred_def_id": credential_definition_id_revocable}
                    ],
                }
            },
            "requested_predicates": {},
        },
        "save_exchange_record": True,
        "connection_id": acme_and_alice_connection.acme_connection_id,
    }
    send_proof_response = await send_proof_request(acme_client, request_body)
    acme_proof_exchange_id = send_proof_response["proof_id"]

    alice_payload = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": send_proof_response["thread_id"],
        },
    )

    alice_proof_exchange_id = alice_payload["proof_id"]

    # Send proof
    await alice_member_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json={
            "proof_id": alice_proof_exchange_id,
            "type": "indy",
            "indy_presentation_spec": {
                "requested_attributes": {
                    "THE_SPEED": {"cred_id": referent, "revealed": True}
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
            "dif_presentation_spec": {},
        },
    )

    await assert_both_webhooks_received(
        alice_member_client,
        acme_client,
        "proofs",
        "done",
        alice_proof_exchange_id,
        acme_proof_exchange_id,
    )

    # Check proof
    proof = (
        await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_exchange_id}")
    ).json()

    assert proof["verified"] is False
