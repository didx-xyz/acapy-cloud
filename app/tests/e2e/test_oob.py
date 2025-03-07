import pytest
from aries_cloudcontroller import AcaPyClient
from assertpy import assert_that

from app.routes.connections import router as connections_router
from app.routes.oob import router
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

OOB_BASE_PATH = router.prefix
CONNECTIONS_BASE_PATH = connections_router.prefix


@pytest.mark.anyio
async def test_create_invitation_oob(
    bob_member_client: RichAsyncClient,
):
    invitation_response = await bob_member_client.post(
        OOB_BASE_PATH + "/create-invitation", json={"create_connection": True}
    )
    assert_that(invitation_response.status_code).is_equal_to(200)
    invitation = invitation_response.json()

    assert_that(invitation).contains("invi_msg_id", "invitation", "invitation_url")
    assert_that(invitation["invitation"]).contains("@id", "services")


@pytest.mark.anyio
async def test_accept_invitation_oob(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    invitation_response = await bob_member_client.post(
        OOB_BASE_PATH + "/create-invitation",
        json={
            "create_connection": True,
            "use_public_did": False,
            "handshake_protocols": ["https://didcomm.org/didexchange/1.0"],
        },
    )
    assert_that(invitation_response.status_code).is_equal_to(200)
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
            f"{CONNECTIONS_BASE_PATH}/{oob_record["connection_id"]}"
        )
    ).json()

    assert_that(accept_response.status_code).is_equal_to(200)
    assert_that(oob_record).contains("created_at", "oob_id", "invitation")
    assert_that(connection_record["connection_protocol"]).contains("didexchange/1.0")


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_oob_connect_via_public_did(
    bob_member_client: RichAsyncClient,
    faber_indy_acapy_client: AcaPyClient,
):
    faber_public_did = await faber_indy_acapy_client.wallet.get_public_did()
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

    assert_that(bob_oob_record).has_their_public_did(faber_public_did.result.did)
