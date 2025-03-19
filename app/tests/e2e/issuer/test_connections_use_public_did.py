import pytest
from assertpy import assert_that

from app.models.connections import AcceptInvitation, CreateInvitation
from app.routes.connections import router
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

CONNECTIONS_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
@pytest.mark.parametrize("issuer_wallet_type", ["indy", "anoncreds"])
async def test_accept_use_public_did(
    issuer_wallet_type: str,
    faber_indy_client: RichAsyncClient,  # issuer has public did
    faber_anoncreds_client: RichAsyncClient,
    meld_co_indy_client: RichAsyncClient,  # also has public did
    meld_co_anoncreds_client: RichAsyncClient,
):
    if issuer_wallet_type == "indy":
        issuer_client = faber_indy_client
        issuer_verifier_client = meld_co_indy_client
    else:
        issuer_client = faber_anoncreds_client
        issuer_verifier_client = meld_co_anoncreds_client

    invite_json = CreateInvitation(use_public_did=True).model_dump()

    response = await issuer_client.post(
        f"{CONNECTIONS_BASE_PATH}/create-invitation", json=invite_json
    )
    assert response.status_code == 200

    invitation = response.json()
    assert_that(invitation["connection_id"]).is_not_empty()
    assert_that(invitation["invitation"]).is_instance_of(dict).contains(
        "@id", "@type", "recipientKeys", "serviceEndpoint"
    )
    assert_that(invitation["invitation_url"]).matches(r"^https?://")

    accept_invite_json = AcceptInvitation(
        invitation=invitation["invitation"],
    ).model_dump()

    accept_response = await issuer_verifier_client.post(
        f"{CONNECTIONS_BASE_PATH}/accept-invitation",
        json=accept_invite_json,
    )
    connection_record = accept_response.json()

    assert_that(connection_record).contains(
        "connection_id", "state", "created_at", "updated_at", "invitation_key"
    )
    assert_that(connection_record).has_state("request-sent")

    assert await check_webhook_state(
        client=issuer_verifier_client,
        topic="connections",
        state="completed",
        filter_map={
            "connection_id": connection_record["connection_id"],
        },
    )


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
@pytest.mark.parametrize("issuer_wallet_type", ["indy", "anoncreds"])
async def test_accept_use_public_did_between_issuer_and_holder(
    issuer_wallet_type: str,
    faber_indy_client: RichAsyncClient,  # issuer has public did
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,  # no public did
):
    if issuer_wallet_type == "indy":
        issuer_client = faber_indy_client
    else:
        issuer_client = faber_anoncreds_client

    invite_json = CreateInvitation(use_public_did=True).model_dump()

    response = await issuer_client.post(
        f"{CONNECTIONS_BASE_PATH}/create-invitation", json=invite_json
    )
    assert response.status_code == 200

    invitation = response.json()
    assert_that(invitation["connection_id"]).is_not_empty()
    assert_that(invitation["invitation"]).is_instance_of(dict).contains(
        "@id", "@type", "recipientKeys", "serviceEndpoint"
    )
    assert_that(invitation["invitation_url"]).matches(r"^https?://")

    accept_invite_json = AcceptInvitation(
        invitation=invitation["invitation"]
    ).model_dump()

    accept_response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/accept-invitation",
        json=accept_invite_json,
    )
    connection_record = accept_response.json()

    assert_that(connection_record).contains(
        "connection_id", "state", "created_at", "updated_at", "invitation_key"
    )
    assert_that(connection_record).has_state("request-sent")

    assert await check_webhook_state(
        client=alice_member_client,
        topic="connections",
        state="completed",
        filter_map={
            "connection_id": connection_record["connection_id"],
        },
    )
