import re

import pytest
from aries_cloudcontroller import AcaPyClient

from app.routes.connections import router as connections_router
from app.routes.oob import router
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

OOB_BASE_PATH = router.prefix
CONNECTIONS_BASE_PATH = connections_router.prefix


@pytest.mark.anyio
async def test_create_invitation_oob(
    bob_member_client: RichAsyncClient,
) -> None:
    invitation_response = await bob_member_client.post(
        OOB_BASE_PATH + "/create-invitation", json={"create_connection": True}
    )
    assert invitation_response.status_code == 200
    invitation = invitation_response.json()

    assert invitation["invi_msg_id"]
    assert invitation["invitation"]
    assert re.match(r"^http(s)?://", invitation["invitation_url"])


@pytest.mark.anyio
async def test_accept_invitation_oob(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
) -> None:
    invitation_response = await bob_member_client.post(
        OOB_BASE_PATH + "/create-invitation",
        json={
            "create_connection": True,
            "use_public_did": False,
            "handshake_protocols": ["https://didcomm.org/didexchange/1.1"],
        },
    )
    assert invitation_response.status_code == 200
    invitation = (invitation_response.json())["invitation"]

    accept_response = await alice_member_client.post(
        OOB_BASE_PATH + "/accept-invitation",
        json={"invitation": invitation},
    )

    oob_record = accept_response.json()
    assert await check_webhook_state(
        client=alice_member_client,
        topic="connections",
        state="completed",
        filter_map={
            "connection_id": oob_record["connection_id"],
        },
    )

    connection_record = (
        await alice_member_client.get(
            f"{CONNECTIONS_BASE_PATH}/{oob_record['connection_id']}"
        )
    ).json()

    assert accept_response.status_code == 200
    assert oob_record["created_at"]
    assert oob_record["oob_id"]
    assert oob_record["invitation"]
    assert connection_record["connection_protocol"]


@pytest.mark.anyio
@pytest.mark.skip(reason="TODO: To be reviewed / fixed for cheqd")
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_oob_connect_via_public_did(
    bob_member_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
) -> None:
    faber_public_did = await faber_anoncreds_acapy_client.wallet.get_public_did()
    connect_response = await bob_member_client.post(
        OOB_BASE_PATH + "/connect-public-did",
        json={"public_did": faber_public_did.result.did},
    )
    bob_oob_record = connect_response.json()

    assert await check_webhook_state(
        client=bob_member_client,
        topic="connections",
        state="request-sent",
        filter_map={
            "connection_id": bob_oob_record["connection_id"],
        },
    )

    assert bob_oob_record["their_public_did"] == faber_public_did.result.did
