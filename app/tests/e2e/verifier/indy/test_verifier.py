import asyncio
import json
import time
from typing import Optional

import pytest
from aries_cloudcontroller import IndyPresSpec, IndyRequestedCredsRequestedAttr
from fastapi import HTTPException

from app.routes.definitions import router as def_router
from app.routes.issuer import router as issuer_router
from app.routes.oob import router as oob_router
from app.routes.verifier import AcceptProofRequest, RejectProofRequest
from app.routes.verifier import router as verifier_router
from app.tests.fixtures.credentials import ReferentCredDef
from app.tests.services.verifier.utils import sample_indy_proof_request
from app.tests.util.connections import AcmeAliceConnect, MeldCoAliceConnect
from app.tests.util.regression_testing import TestMode
from app.tests.util.verifier import send_proof_request
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange
from shared.models.presentation_exchange import PresentationExchange

DEFINITIONS_BASE_PATH = def_router.prefix
ISSUER_BASE_PATH = issuer_router.prefix
OOB_BASE_PATH = oob_router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix


@pytest.mark.anyio
async def test_send_proof_request(
    acme_and_alice_connection: AcmeAliceConnect,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": sample_indy_proof_request().to_dict(),
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    try:
        assert "presentation" in send_proof_response
        assert "presentation_request" in send_proof_response
        assert "created_at" in send_proof_response
        assert "proof_id" in send_proof_response
        assert send_proof_response["role"] == "verifier"
        assert send_proof_response["state"]

        thread_id = send_proof_response["thread_id"]
        assert thread_id

        await check_webhook_state(
            client=alice_member_client,
            topic="proofs",
            state="request-received",
            filter_map={
                "thread_id": thread_id,
            },
        )

    finally:
        # Clean up:
        await acme_client.delete(
            VERIFIER_BASE_PATH + f"/proofs/{send_proof_response['proof_id']}",
        )


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group_3")
async def test_accept_proof_request(
    issue_indy_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    alice_member_client: RichAsyncClient,
    acme_client: RichAsyncClient,
    indy_credential_definition_id: str,
    acme_and_alice_connection: AcmeAliceConnect,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": {
            "name": "Proof Request",
            "version": "1.0.0",
            "requested_attributes": {
                "0_speed_uuid": {
                    "name": "speed",
                    "restrictions": [{"cred_def_id": indy_credential_definition_id}],
                }
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

    requested_credentials = await alice_member_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
    )

    referent = requested_credentials.json()[0]["cred_info"]["referent"]
    indy_request_attrs = IndyRequestedCredsRequestedAttr(
        cred_id=referent, revealed=True
    )
    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={"0_speed_uuid": indy_request_attrs},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    response = await alice_member_client.post(
        VERIFIER_BASE_PATH + "/accept-request",
        json=proof_accept.model_dump(),
    )

    result = response.json()

    pres_exchange_result = PresentationExchange(**result)
    assert isinstance(pres_exchange_result, PresentationExchange)

    assert await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="done",
        filter_map={
            "proof_id": alice_proof_id,
        },
    )

    acme_proof_event = await check_webhook_state(
        client=acme_client,
        topic="proofs",
        state="done",
        filter_map={
            "proof_id": acme_proof_id,
        },
    )
    assert acme_proof_event["verified"] is True


@pytest.mark.anyio
@pytest.mark.parametrize("delete_proof_record", [True, False])
async def test_reject_proof_request(
    acme_and_alice_connection: AcmeAliceConnect,
    alice_member_client: RichAsyncClient,
    acme_client: RichAsyncClient,
    delete_proof_record: bool,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": sample_indy_proof_request().to_dict(),
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    thread_id = send_proof_response["thread_id"]
    assert thread_id

    alice_exchange = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    reject_proof_request = RejectProofRequest(
        proof_id=alice_exchange["proof_id"],
        problem_report="rejected",
        delete_proof_record=delete_proof_record,
    )

    response = await alice_member_client.post(
        VERIFIER_BASE_PATH + "/reject-request",
        json=reject_proof_request.model_dump(),
    )
    assert response.status_code == 204

    # assert that record has transitioned to "abandoned" state
    alice_abandoned_webhook = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="abandoned",
        filter_map={
            "thread_id": thread_id,
        },
    )
    assert alice_abandoned_webhook["error_msg"] == "created problem report: rejected"

    # assert that record has transitioned to "abandoned" state
    acme_abandoned_webhook = await check_webhook_state(
        client=acme_client,
        topic="proofs",
        state="abandoned",
        filter_map={
            "thread_id": thread_id,
        },
    )
    assert acme_abandoned_webhook["error_msg"] == "abandoned: rejected"

    # assert that alice has webhook for "deleted" state change
    if delete_proof_record:
        await check_webhook_state(
            client=alice_member_client,
            topic="proofs",
            state="deleted",
            filter_map={
                "thread_id": thread_id,
            },
        )


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_proof_and_get_proofs(
    acme_and_alice_connection: AcmeAliceConnect,
    issue_indy_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    indy_credential_definition_id: str,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    acme_connection_id = acme_and_alice_connection.acme_connection_id

    request_body = {
        "save_exchange_record": True,
        "connection_id": acme_connection_id,
        "indy_proof_request": sample_indy_proof_request(
            restrictions=[{"cred_def_id": indy_credential_definition_id}]
        ).to_dict(),
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    # Assert that getting single proof record works
    acme_proof_id = send_proof_response["proof_id"]
    thread_id = send_proof_response["thread_id"]

    response = await acme_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}",
    )
    result = response.json()
    assert "connection_id" in result
    assert "created_at" in result
    assert "updated_at" in result
    assert "presentation" in result
    assert "presentation_request" in result

    await asyncio.sleep(0.3)  # allow moment for alice records to update

    # Fetch proofs for alice
    alice_payload = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": thread_id,
        },
    )
    alice_proof_id = alice_payload["proof_id"]

    # Get credential referent for alice to accept request
    referent = (
        await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
        )
    ).json()[0]["cred_info"]["referent"]

    indy_request_attrs = IndyRequestedCredsRequestedAttr(
        cred_id=referent, revealed=True
    )

    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={"0_speed_uuid": indy_request_attrs},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    # Alice accepts
    await alice_member_client.post(
        VERIFIER_BASE_PATH + "/accept-request",
        json=proof_accept.model_dump(),
    )

    await assert_both_webhooks_received(
        alice_member_client,
        acme_client,
        "proofs",
        "done",
        alice_proof_id,
        acme_proof_id,
    )

    acme_proof_exchange = (
        await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}")
    ).json()

    # Make sure the proof is done
    assert acme_proof_exchange["state"] == "done"

    # Acme does proof request and alice does not respond
    request_body = {
        "save_exchange_record": True,
        "connection_id": acme_connection_id,
        "indy_proof_request": sample_indy_proof_request().to_dict(),
    }
    send_proof_response_2 = await send_proof_request(acme_client, request_body)

    acme_proof_id_2 = send_proof_response_2["proof_id"]
    thread_id_2 = send_proof_response_2["thread_id"]

    all_verifier_proofs = (
        await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs", params={"limit": 10000})
    ).json()
    all_verifier_proofs = [proof["proof_id"] for proof in all_verifier_proofs]

    # Make sure both proofs are in the list
    proof_ids = [acme_proof_id, acme_proof_id_2]

    try:
        assert sum(1 for proof in proof_ids if proof in all_verifier_proofs) == 2

        # Now test query params
        proofs_sent = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?state=request-sent"
        )
        for proof in proofs_sent.json():
            assert proof["state"] == "request-sent"

        proofs_done = await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs?state=done")
        for proof in proofs_done.json():
            assert proof["state"] == "done"

        proofs_role = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?role=verifier"
        )
        for proof in proofs_role.json():
            assert proof["role"] == "verifier"

        proofs_prover = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?role=prover"
        )
        assert len(proofs_prover.json()) == 0

        proofs = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?connection_id={acme_connection_id}&state=done"
        )
        assert len(proofs.json()) >= 1

        proofs = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?connection_id={acme_connection_id}&state=request-sent"
        )
        assert len(proofs.json()) >= 1

        proofs = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?connection_id={acme_connection_id}&thread_id={thread_id}"
        )
        assert len(proofs.json()) == 1

        proofs = await acme_client.get(
            f"{VERIFIER_BASE_PATH}/proofs?connection_id={acme_connection_id}&thread_id={thread_id_2}"
        )
        assert len(proofs.json()) == 1

        with pytest.raises(HTTPException) as exc:
            await acme_client.get(
                f"{VERIFIER_BASE_PATH}/proofs?connection_id=123&state=invalid&role=invalid&thread_id=invalid"
            )
        assert exc.value.status_code == 422
        assert len(json.loads(exc.value.detail)["detail"]) == 3

    finally:
        # Clean up:
        for proof_id in proof_ids:
            await acme_client.delete(VERIFIER_BASE_PATH + f"/proofs/{proof_id}")


@pytest.mark.anyio
async def test_delete_proof(
    acme_and_alice_connection: AcmeAliceConnect,
    acme_client: RichAsyncClient,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": sample_indy_proof_request().to_dict(),
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    proof_id = send_proof_response["proof_id"]

    response = await acme_client.delete(
        VERIFIER_BASE_PATH + f"/proofs/{proof_id}",
    )
    assert response.status_code == 204


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group_3")
async def test_get_credentials_for_request(
    issue_indy_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    acme_and_alice_connection: AcmeAliceConnect,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": sample_indy_proof_request().to_dict(),
    }
    send_proof_response = await send_proof_request(acme_client, request_body)

    try:
        thread_id = send_proof_response["thread_id"]
        assert thread_id

        alice_exchange = await check_webhook_state(
            client=alice_member_client,
            topic="proofs",
            state="request-received",
            filter_map={
                "thread_id": thread_id,
            },
        )

        proof_id = alice_exchange["proof_id"]

        response = await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{proof_id}/credentials",
        )

        result = response.json()[0]
        assert "cred_info" in result
        assert result["cred_info"]["referent"] == result["cred_info"]["credential_id"]
        assert [
            attr
            in [
                "attrs",
                "cred_def_info",
                "referent",
                "credential_id",
                "interval",
                "presentation_referents",
            ]
            for attr in result["cred_info"]
        ]

    finally:
        # Clean up:
        await acme_client.delete(
            VERIFIER_BASE_PATH + f"/proofs/{send_proof_response['proof_id']}",
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "meld_co_indy_and_alice_connection", ["trust_registry", "default"], indirect=True
)
@pytest.mark.xdist_group(name="issuer_test_group_3")
async def test_accept_proof_request_verifier_has_issuer_role(
    meld_co_issue_indy_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    meld_co_indy_credential_definition_id: str,
    alice_member_client: RichAsyncClient,
    meld_co_indy_client: RichAsyncClient,
    meld_co_indy_and_alice_connection: MeldCoAliceConnect,
):
    request_body = {
        "connection_id": meld_co_indy_and_alice_connection.meld_co_connection_id,
        "indy_proof_request": sample_indy_proof_request(
            restrictions=[{"cred_def_id": meld_co_indy_credential_definition_id}]
        ).to_dict(),
    }
    send_proof_response = await send_proof_request(meld_co_indy_client, request_body)

    meld_co_proof_id = send_proof_response["proof_id"]
    thread_id = send_proof_response["thread_id"]

    alice_payload = await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={"thread_id": thread_id},
    )
    alice_proof_id = alice_payload["proof_id"]

    requested_credentials = await alice_member_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
    )

    assert await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "proof_id": alice_proof_id,
        },
    )

    referent = requested_credentials.json()[0]["cred_info"]["referent"]
    indy_request_attrs = IndyRequestedCredsRequestedAttr(
        cred_id=referent, revealed=True
    )

    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={"0_speed_uuid": indy_request_attrs},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    response = await alice_member_client.post(
        VERIFIER_BASE_PATH + "/accept-request",
        json=proof_accept.model_dump(),
    )

    await assert_both_webhooks_received(
        alice_member_client,
        meld_co_indy_client,
        "proofs",
        "done",
        alice_proof_id,
        meld_co_proof_id,
    )

    pres_exchange_result = PresentationExchange(**response.json())
    assert isinstance(pres_exchange_result, PresentationExchange)


@pytest.mark.anyio
@pytest.mark.parametrize("acme_save_exchange_record", [None, False, True])
@pytest.mark.parametrize("alice_save_exchange_record", [None, False, True])
@pytest.mark.xdist_group(name="issuer_test_group_4")
async def test_saving_of_presentation_exchange_records(
    issue_indy_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    indy_credential_definition_id: str,
    alice_member_client: RichAsyncClient,
    acme_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
    acme_save_exchange_record: Optional[bool],
    alice_save_exchange_record: Optional[bool],
):
    request_body = {
        "connection_id": acme_and_alice_connection.acme_connection_id,
        "indy_proof_request": sample_indy_proof_request(
            restrictions=[{"cred_def_id": indy_credential_definition_id}]
        ).to_dict(),
        "save_exchange_record": acme_save_exchange_record,
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

    requested_credentials = await alice_member_client.get(
        f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}/credentials"
    )

    referent = requested_credentials.json()[0]["cred_info"]["referent"]
    indy_request_attrs = IndyRequestedCredsRequestedAttr(
        cred_id=referent, revealed=True
    )

    proof_accept = AcceptProofRequest(
        proof_id=alice_proof_id,
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={"0_speed_uuid": indy_request_attrs},
            requested_predicates={},
            self_attested_attributes={},
        ),
        save_exchange_record=alice_save_exchange_record,
    )

    response = await alice_member_client.post(
        VERIFIER_BASE_PATH + "/accept-request",
        json=proof_accept.model_dump(),
    )
    result = response.json()

    pres_exchange_result = PresentationExchange(**result)
    assert isinstance(pres_exchange_result, PresentationExchange)
    assert response.status_code == 200

    await assert_both_webhooks_received(
        alice_member_client,
        acme_client,
        "proofs",
        "done",
        alice_proof_id,
        acme_proof_id,
    )

    await asyncio.sleep(1)  # short sleep before fetching records; allow them to update
    # get exchange records from alice side
    if alice_save_exchange_record:
        # Save record is True, should be 1 record
        alice_pres_ex_record = (
            await alice_member_client.get(
                f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}"
            )
        ).json()
        assert alice_pres_ex_record
    else:
        # default is to remove records
        with pytest.raises(HTTPException) as exc:
            await alice_member_client.get(
                f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_id}"
            )
        assert exc.value.status_code == 404

    # get exchange records from acme side
    if acme_save_exchange_record:
        # Save record is True, should be 1 record
        acme_pres_ex_record = (
            await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}")
        ).json()
        assert acme_pres_ex_record
    else:
        # default is to remove records
        with pytest.raises(HTTPException) as exc:
            await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_id}")
        assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.clean_run in TestMode.fixture_params,
    reason="Run only in regression mode",
)
@pytest.mark.xdist_group(name="issuer_test_group_3")
async def test_regression_proof_valid_indy_credential(
    get_or_issue_regression_indy_cred_valid: ReferentCredDef,
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    acme_and_alice_connection: AcmeAliceConnect,
):
    unix_timestamp = int(time.time())
    referent = get_or_issue_regression_indy_cred_valid.referent
    credential_definition_id_revocable = (
        get_or_issue_regression_indy_cred_valid.cred_def_revocable
    )

    # Do proof request
    request_body = {
        "comment": "Test cred is not revoked",
        "type": "indy",
        "indy_proof_request": {
            "non_revoked": {"to": unix_timestamp},
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

    assert proof["verified"] is True
