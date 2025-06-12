import asyncio
from copy import deepcopy

import pytest
from aries_cloudcontroller import AcaPyClient

from app.routes.issuer import router as issuer_router
from app.routes.oob import router as oob_router
from app.routes.wallet.dids import router as wallet_router
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient

from .util import create_credential

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group_3")
pytestmark = pytest.mark.skip(reason="TODO: To be reviewed / fixed for cheqd")

CREDENTIALS_BASE_PATH = issuer_router.prefix
OOB_BASE_PATH = oob_router.prefix
WALLET = wallet_router.prefix

credential_ = create_credential("Ed25519Signature2020")


@pytest.mark.anyio
async def test_send_jsonld_credential_cheqd(
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> None:
    alice_connection_id = faber_anoncreds_and_alice_connection.alice_connection_id
    faber_connection_id = faber_anoncreds_and_alice_connection.faber_connection_id

    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did

    # Updating JSON-LD credential
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"]["issuer"] = faber_pub_did

    # Send credential
    response = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )

    data = response.json()
    assert data["credential_exchange_id"]
    assert data["state"] == "offer-sent"
    cred_ex_id = data["credential_exchange_id"]

    try:
        thread_id = data["thread_id"]
        assert await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        )

        # Check if Alice received the credential
        response = await alice_member_client.get(
            CREDENTIALS_BASE_PATH,
            params={"thread_id": thread_id},
        )

        records = response.json()

        assert len(records) == 1

        # Check if the received credential matches the sent one
        received_credential = records[-1]
        assert received_credential["connection_id"] == alice_connection_id
        assert received_credential["state"] == "offer-received"
        assert received_credential["role"] == "holder"
        assert received_credential["credential_exchange_id"].startswith("v2")

    finally:
        # Clean up created offer
        await faber_anoncreds_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_jsonld_oob_cheqd(
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> None:
    faber_connection_id = faber_anoncreds_and_alice_connection.faber_connection_id

    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did

    # Updating JSON-LD credential
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"]["issuer"] = faber_pub_did

    # faber create offer
    response = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH + "/create-offer",
        json=credential,
    )

    data = response.json()
    assert data["credential_exchange_id"]
    assert data["state"] == "offer-sent"
    cred_ex_id = data["credential_exchange_id"]

    try:
        thread_id = data["thread_id"]
        invitation_response = await faber_anoncreds_client.post(
            OOB_BASE_PATH + "/create-invitation",
            json={
                "create_connection": False,
                "use_public_did": False,
                "attachments": [
                    {
                        "id": data["credential_exchange_id"][3:],
                        "type": "credential-offer",
                    }
                ],
            },
        )
        assert invitation_response.status_code == 200

        invitation = (invitation_response.json())["invitation"]

        accept_response = await alice_member_client.post(
            OOB_BASE_PATH + "/accept-invitation",
            json={"invitation": invitation},
        )

        oob_record = accept_response.json()

        assert accept_response.status_code == 200
        assert oob_record["created_at"]
        assert oob_record["oob_id"]
        assert oob_record["invitation"]
        assert await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={"thread_id": thread_id},
        )

    finally:
        # Clean up created offer
        await faber_anoncreds_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_jsonld_request_cheqd(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> None:
    faber_connection_id = faber_anoncreds_and_alice_connection.faber_connection_id

    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did
    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"]["issuer"] = faber_pub_did

    response = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]

    assert await check_webhook_state(
        client=faber_anoncreds_client,
        topic="credentials",
        state="offer-sent",
        filter_map={
            "thread_id": thread_id,
        },
    )

    assert await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="offer-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    response = await alice_member_client.get(
        CREDENTIALS_BASE_PATH,
        params={"thread_id": thread_id},
    )

    credential_exchange_id = (response.json())[0]["credential_exchange_id"]

    request_response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{credential_exchange_id}/request",
    )

    assert request_response.status_code == 200

    result = await asyncio.gather(
        check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="request-sent",
            filter_map={
                "thread_id": thread_id,
            },
        ),
        check_webhook_state(
            client=faber_anoncreds_client,
            topic="credentials",
            state="request-received",
            filter_map={
                "thread_id": thread_id,
            },
        ),
    )
    assert all(result), "An expected webhook event was not returned"


@pytest.mark.anyio
async def test_issue_jsonld_cheqd(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> None:
    faber_connection_id = faber_anoncreds_and_alice_connection.faber_connection_id

    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did
    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"]["issuer"] = faber_pub_did

    response = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]
    faber_cred_ex_id = credential_exchange["credential_exchange_id"]

    assert await check_webhook_state(
        client=faber_anoncreds_client,
        topic="credentials",
        state="offer-sent",
        filter_map={
            "thread_id": thread_id,
        },
    )

    assert await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="offer-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    response = await alice_member_client.get(
        CREDENTIALS_BASE_PATH,
        params={"thread_id": thread_id},
    )

    alice_cred_ex_id = (response.json())[0]["credential_exchange_id"]

    request_response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_cred_ex_id}/request",
    )

    assert request_response.status_code == 200

    await assert_both_webhooks_received(
        alice_member_client,
        faber_anoncreds_client,
        "credentials",
        "done",
        alice_cred_ex_id,
        faber_cred_ex_id,
    )
