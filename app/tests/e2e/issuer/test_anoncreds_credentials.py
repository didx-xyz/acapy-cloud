import asyncio

import pytest

from app.routes.definitions import CredentialSchema
from app.routes.issuer import router as issuer_router
from app.routes.oob import router as oob_router
from app.tests.fixtures.credentials import sample_credential_attributes
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group")

CREDENTIALS_BASE_PATH = issuer_router.prefix
OOB_BASE_PATH = oob_router.prefix


@pytest.mark.anyio
async def test_send_credential_oob(
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_schema_definition: CredentialSchema,
    anoncreds_credential_definition_id: str,
    alice_member_client: RichAsyncClient,
):
    credential = {
        "type": "anoncreds",
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id,
            "attributes": sample_credential_attributes,
        },
    }

    response = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH + "/create-offer", json=credential
    )

    data = response.json()
    assert data["credential_exchange_id"]
    assert data["state"] == "offer-sent"
    assert data["attributes"] == sample_credential_attributes
    assert data["schema_id"] == anoncreds_schema_definition.id

    cred_ex_id = data["credential_exchange_id"]

    try:
        invitation_response = await faber_anoncreds_client.post(
            OOB_BASE_PATH + "/create-invitation",
            json={
                "create_connection": False,
                "use_public_did": False,
                "attachments": [{"id": cred_ex_id[3:], "type": "credential-offer"}],
            },
        )
        assert invitation_response.status_code == 200

        invitation = (invitation_response.json())["invitation"]
        thread_id = invitation["requests~attach"][0]["data"]["json"]["@id"]

        accept_response = await alice_member_client.post(
            OOB_BASE_PATH + "/accept-invitation", json={"invitation": invitation}
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
            filter_map={
                "thread_id": thread_id,
            },
        )

    finally:
        # Clean up created offer
        await faber_anoncreds_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")


@pytest.mark.anyio
async def test_send_credential_and_request(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    anoncreds_credential_definition_id: str,
):
    credential = {
        "connection_id": faber_anoncreds_and_alice_connection.faber_connection_id,
        "type": "anoncreds",
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id,
            "attributes": sample_credential_attributes,
        },
    }

    response = await faber_anoncreds_client.post(CREDENTIALS_BASE_PATH, json=credential)
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

    await asyncio.sleep(0.5)  # credential may take moment to reflect after webhook
    response = await alice_member_client.get(
        CREDENTIALS_BASE_PATH, params={"thread_id": thread_id}
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
async def test_revoke_credential(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
):
    faber_connection_id = faber_anoncreds_and_alice_connection.faber_connection_id

    credential = {
        "connection_id": faber_connection_id,
        "type": "anoncreds",
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id_revocable,
            "attributes": sample_credential_attributes,
        },
    }

    # create and send credential offer: issuer
    faber_credential_response = (
        await faber_anoncreds_client.post(CREDENTIALS_BASE_PATH, json=credential)
    ).json()
    thread_id = faber_credential_response["thread_id"]
    faber_credential_exchange_id = faber_credential_response["credential_exchange_id"]

    payload = await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="offer-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    alice_credential_exchange_id = payload["credential_exchange_id"]

    # send credential request: holder
    await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}/request", json={}
    )

    await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_exchange_id": alice_credential_exchange_id,
        },
    )

    response = await faber_anoncreds_client.post(
        f"{CREDENTIALS_BASE_PATH}/revoke",
        json={
            "credential_exchange_id": faber_credential_exchange_id,
            "auto_publish_on_ledger": True,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["cred_rev_ids_published"]) == 1
