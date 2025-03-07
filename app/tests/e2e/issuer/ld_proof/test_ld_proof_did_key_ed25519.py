import asyncio
from copy import deepcopy

import pytest
from assertpy import assert_that
from fastapi import HTTPException

from app.routes.connections import router as conn_router
from app.routes.issuer import router as issuer_router
from app.routes.oob import router as oob_router
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from shared import RichAsyncClient

from .util import create_credential

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group_4")

CREDENTIALS_BASE_PATH = issuer_router.prefix
OOB_BASE_PATH = oob_router.prefix
CONNECTIONS_BASE_PATH = conn_router.prefix

credential_ = create_credential("Ed25519Signature2018")


@pytest.mark.anyio
async def test_send_jsonld_key_ed25519(
    faber_indy_client: RichAsyncClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
    register_issuer_key_ed25519: str,
):
    alice_connection_id = faber_indy_and_alice_connection.alice_connection_id
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = register_issuer_key_ed25519

    # Send credential
    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )

    data = response.json()
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
async def test_send_jsonld_oob(
    faber_indy_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    register_issuer_key_ed25519: str,
):
    invitation_response = await faber_indy_client.post(
        OOB_BASE_PATH + "/create-invitation",
        json={
            "create_connection": True,
            "use_public_did": False,
            "attachments": [],
        },
    )

    invitation = (invitation_response.json())["invitation"]

    accept_response = await alice_member_client.post(
        OOB_BASE_PATH + "/accept-invitation",
        json={"invitation": invitation},
    )

    oob_record = accept_response.json()
    assert_that(oob_record).contains("created_at", "oob_id", "invitation")

    alice_connection_id = oob_record["connection_id"]

    assert await check_webhook_state(
        client=alice_member_client,
        topic="connections",
        state="completed",
        filter_map={
            "connection_id": alice_connection_id,
        },
    )

    await asyncio.sleep(0.5)  # connection may take moment to reflect

    faber_connections_response = await faber_indy_client.get(
        CONNECTIONS_BASE_PATH, params={"invitation_msg_id": invitation["@id"]}
    )
    faber_connections = faber_connections_response.json()

    assert faber_connections, "The expected faber-alice connection was not returned"

    faber_connection_id = faber_connections[0]["connection_id"]

    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = register_issuer_key_ed25519

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
        assert await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "connection_id": alice_connection_id,
            },
        )

    finally:
        # Clean up created offer
        await faber_indy_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_jsonld_request(
    alice_member_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    register_issuer_key_ed25519: str,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = register_issuer_key_ed25519

    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]
    faber_cred_ex_id = credential_exchange["credential_exchange_id"]

    result = await asyncio.gather(
        check_webhook_state(
            client=faber_indy_client,
            topic="credentials",
            state="offer-sent",
            filter_map={
                "thread_id": thread_id,
            },
        ),
        check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        ),
    )
    assert all(result), "An expected webhook event was not returned"

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


@pytest.mark.anyio
async def test_issue_jsonld_ed(
    alice_member_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    register_issuer_key_ed25519: str,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    # Updating JSON-LD credential did:key with proofType ed25519
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = register_issuer_key_ed25519

    response = await faber_indy_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    credential_exchange = response.json()
    thread_id = credential_exchange["thread_id"]
    faber_cred_ex_id = credential_exchange["credential_exchange_id"]

    result = await asyncio.gather(
        check_webhook_state(
            client=faber_indy_client,
            topic="credentials",
            state="offer-sent",
            filter_map={
                "thread_id": thread_id,
            },
        ),
        check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        ),
    )
    assert all(result), "An expected webhook event was not returned"

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


# Fail cases:


@pytest.mark.anyio
async def test_send_jsonld_mismatch_ed_bbs(
    faber_indy_client: RichAsyncClient,
    faber_indy_and_alice_connection: FaberAliceConnect,
    register_issuer_key_ed25519: str,
):
    faber_connection_id = faber_indy_and_alice_connection.faber_connection_id

    # Creating JSON-LD credential did:key with proofType: BbsBlsSignature2020
    credential = deepcopy(credential_)
    credential["connection_id"] = faber_connection_id
    credential["ld_credential_detail"]["credential"][
        "issuer"
    ] = register_issuer_key_ed25519
    credential["ld_credential_detail"]["options"] = {"proofType": "BbsBlsSignature2020"}

    # Send credential must fail did:key made with ed25519 mismatch with proofType:BbsBlsSignature2020
    with pytest.raises(HTTPException) as exc:
        await faber_indy_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
    assert exc.value.status_code == 400
