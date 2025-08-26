import asyncio
import time

import pytest

from app.routes.issuer import router as issuer_router
from app.routes.verifier import router as verifier_router
from app.tests.util.connections import AcmeAliceConnect, FaberAliceConnect
from app.tests.util.issuer import issue_many_credentials, revoke_many
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = issuer_router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix


@pytest.mark.anyio
@pytest.mark.skip("This test exists for local testing")
@pytest.mark.parametrize("revoke_many", ["auto_publish_true"], indirect=True)
@pytest.mark.xdist_group(name="issuer_test_group_2")
async def test_revoke_many_credentials(
    revoke_many: list[  # pylint: disable=unused-argument, redefined-outer-name
        CredentialExchange
    ],
    anoncreds_credential_definition_id_revocable: str,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
):
    await asyncio.sleep(10)  # moment for revocation registry to update
    # todo: remove sleep when issue resolved: https://github.com/openwallet-foundation/acapy/issues/3018

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
                    "restrictions": [
                        {"cred_def_id": anoncreds_credential_definition_id_revocable}
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
    ).json()[0]["cred_info"]["credential_id"]

    # Send proof
    await alice_member_client.post(
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


@pytest.fixture(scope="function")
async def revoke_many_fixture(
    request,
    faber_anoncreds_client: RichAsyncClient,
    issue_many_credentials_fixture: list[CredentialExchange],  # pylint: disable=redefined-outer-name
) -> list[CredentialExchange]:
    auto_publish = True
    if hasattr(request, "param") and request.param == "auto_publish_false":
        auto_publish = False

    return await revoke_many(
        faber_anoncreds_client,
        issue_many_credentials_fixture,
        auto_publish,
    )


@pytest.fixture(scope="function")
async def issue_many_credentials_fixture(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    num_to_issue: int = 15,
) -> list[CredentialExchange]:
    return await issue_many_credentials(
        faber_anoncreds_client,
        alice_member_client,
        anoncreds_credential_definition_id_revocable,
        faber_anoncreds_and_alice_connection,
        num_to_issue,
    )
