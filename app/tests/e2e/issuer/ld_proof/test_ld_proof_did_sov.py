import asyncio
from copy import deepcopy

import pytest
from aries_cloudcontroller import AcaPyClient
from assertpy import assert_that

from app.routes.issuer import router as issuer_router
from app.routes.oob import router as oob_router
from app.routes.wallet.dids import router as wallet_router
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient

from .util import create_credential

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group_3")

CREDENTIALS_BASE_PATH = issuer_router.prefix
OOB_BASE_PATH = oob_router.prefix
WALLET = wallet_router.prefix

credential_ = create_credential("Ed25519Signature2018")


@pytest.mark.anyio
async def test_send_jsonld_credential_sov(
    faber_indy_client: RichAsyncClient,
    faber_indy_acapy_client: AcaPyClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
):
    alice_connection_id = faber_indy_and_alice_connection.alice_connection_id
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    faber_pub_did = (await faber_indy_acapy_client.wallet.get_public_did()).result.did

    # Updating JSON-LD credential did:sov
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = f"did:sov:{faber_pub_did}"

    # Send credential
    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )

    data = response.json()
    assert_that(data).contains("credential_exchange_id")
    assert_that(data).has_state("offer-sent")
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
        await asyncio.sleep(0.5)  # credential may take moment to reflect after webhook
        response = await alice_member_client.get(
            CREDENTIALS_BASE_PATH,
            params={"thread_id": thread_id},
        )

        records = response.json()

        assert len(records) == 1

        # Check if the received credential matches the sent one
        received_credential = records[-1]
        assert_that(received_credential).has_connection_id(alice_connection_id)
        assert_that(received_credential).has_state("offer-received")
        assert_that(received_credential).has_role("holder")
        assert_that(received_credential["credential_exchange_id"]).starts_with("v2")

    finally:
        # Clean up created offer
        await faber_indy_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_jsonld_oob_sov(
    faber_indy_client: RichAsyncClient,
    faber_indy_acapy_client: AcaPyClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    faber_pub_did = (await faber_indy_acapy_client.wallet.get_public_did()).result.did

    # Updating JSON-LD credential did:sov
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = f"did:sov:{faber_pub_did}"

    # faber create offer
    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH + "/create-offer",
        json=credential,
    )

    data = response.json()
    assert_that(data).contains("credential_exchange_id")
    assert_that(data).has_state("offer-sent")
    cred_ex_id = data["credential_exchange_id"]

    try:
        thread_id = data["thread_id"]
        invitation_response = await faber_indy_client.post(
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
        assert_that(invitation_response.status_code).is_equal_to(200)

        invitation = (invitation_response.json())["invitation"]

        accept_response = await alice_member_client.post(
            OOB_BASE_PATH + "/accept-invitation",
            json={"invitation": invitation},
        )

        oob_record = accept_response.json()

        assert_that(accept_response.status_code).is_equal_to(200)
        assert_that(oob_record).contains("created_at", "oob_id", "invitation")
        assert await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={"thread_id": thread_id},
        )

    finally:
        # Clean up created offer
        await faber_indy_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_jsonld_request_sov(
    alice_member_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
    faber_indy_acapy_client: AcaPyClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    faber_pub_did = (await faber_indy_acapy_client.wallet.get_public_did()).result.did
    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = f"did:sov:{faber_pub_did}"

    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]

    assert await check_webhook_state(
        client=faber_indy_client,
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

    await asyncio.sleep(0.5)  # credential may take moment to reflect after webhook
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
            client=faber_indy_client,
            topic="credentials",
            state="request-received",
            filter_map={
                "thread_id": thread_id,
            },
        ),
    )
    assert all(result), "An expected webhook event was not returned"


@pytest.mark.anyio
async def test_issue_jsonld_sov(
    alice_member_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
    faber_indy_acapy_client: AcaPyClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    faber_pub_did = (await faber_indy_acapy_client.wallet.get_public_did()).result.did
    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = f"did:sov:{faber_pub_did}"

    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]
    faber_cred_ex_id = credential_exchange["credential_exchange_id"]

    assert await check_webhook_state(
        client=faber_indy_client,
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

    await asyncio.sleep(0.5)  # credential may take moment to reflect after webhook
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
        faber_indy_client,
        "credentials",
        "done",
        alice_cred_ex_id,
        faber_cred_ex_id,
    )
