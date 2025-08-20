import pytest
from aries_cloudcontroller import AcaPyClient
from fastapi import HTTPException

from app.models.wallet import DIDCreate
from app.routes.connections import router as connections_router
from app.services import acapy_wallet
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

CONNECTIONS_BASE_PATH = connections_router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize("did_method", ["did:peer:2", "did:peer:4"])
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_rotate_did(
    alice_member_client: RichAsyncClient,
    alice_acapy_client: AcaPyClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    did_method: str,
):
    # First, create did-exchange connections between Alice and Faber:
    faber_public_did = await acapy_wallet.get_public_did(
        controller=faber_anoncreds_acapy_client
    )

    request_data = {"their_public_did": faber_public_did.did}
    response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request", params=request_data
    )
    connection_record = response.json()

    alice_connection_id = connection_record["connection_id"]
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        state="completed",
        filter_map={"connection_id": alice_connection_id},
    )

    # Create a new did for Alice and rotate
    did_create_request = DIDCreate(method=did_method)
    new_did = await acapy_wallet.create_did(
        controller=alice_acapy_client, did_create=did_create_request
    )
    alice_new_did = new_did.did

    rotate_response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/did-rotate",
        params={"connection_id": alice_connection_id, "to_did": alice_new_did},
    )
    assert rotate_response.status_code == 200
    rotate_data = rotate_response.json()
    assert rotate_data["to_did"] == alice_new_did


@pytest.mark.anyio
@pytest.mark.skip(reason="TODO: To be reviewed / fixed for cheqd")
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_hangup_did_rotation(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
):
    # First, create did-exchange connections between Alice and Faber:
    faber_public_did = await acapy_wallet.get_public_did(
        controller=faber_anoncreds_acapy_client
    )

    request_data = {"their_public_did": faber_public_did.did}
    response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request", params=request_data
    )
    connection_record = response.json()

    alice_connection_id = connection_record["connection_id"]
    alice_did = connection_record["my_did"]
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        state="completed",
        filter_map={"connection_id": alice_connection_id},
    )

    faber_event = await check_webhook_state(
        faber_anoncreds_client,
        topic="connections",
        state="completed",
        filter_map={"their_did": alice_did},
    )
    faber_connection_id = faber_event["connection_id"]

    # Hangup the DID rotation
    hangup_response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/did-rotate/hangup",
        params={"connection_id": alice_connection_id},
    )
    assert hangup_response.status_code == 200

    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        state="deleted",
        filter_map={"connection_id": alice_connection_id},
    )
    assert await check_webhook_state(
        faber_anoncreds_client,
        topic="connections",
        state="deleted",
        filter_map={"connection_id": faber_connection_id},
    )

    # Verify connection records no longer exist for both Alice and Faber
    with pytest.raises(HTTPException) as exc_info:
        await alice_member_client.get(f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}")
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await faber_anoncreds_client.get(
            f"{CONNECTIONS_BASE_PATH}/{faber_connection_id}"
        )
    assert exc_info.value.status_code == 404
