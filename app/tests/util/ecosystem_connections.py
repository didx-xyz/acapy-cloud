from dataclasses import dataclass
from typing import Any, Dict, TypedDict

import pytest
from aries_cloudcontroller import AcaPyClient

from app.models.tenants import CreateTenantResponse
from app.routes.connections import CreateInvitation
from app.routes.connections import router as conn_router
from app.routes.oob import router as oob_router
from app.services.event_handling.sse_listener import SseListener
from app.services.trust_registry import actors
from app.services.trust_registry.actors import fetch_actor_by_id
from app.tests.util.ledger import create_public_did
from app.tests.util.webhooks import check_webhook_state
from app.util.acapy_verifier_utils import ed25519_verkey_to_did_key
from app.util.string import base64_to_json
from shared import RichAsyncClient

OOB_BASE_PATH = oob_router.prefix
CONNECTIONS_BASE_PATH = conn_router.prefix


@dataclass
class BobAliceConnect:
    alice_connection_id: str
    bob_connection_id: str


@pytest.fixture(scope="function")
async def bob_and_alice_connection(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
) -> BobAliceConnect:
    # create invitation on bob side
    json_request = CreateInvitation(
        alias="bob",
        multi_use=False,
        use_public_did=False,
    ).model_dump()
    invitation = (
        await bob_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/create-invitation", json=json_request
        )
    ).json()

    # accept invitation on alice side
    invitation_response = (
        await alice_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/accept-invitation",
            json={"alias": "alice", "invitation": invitation["invitation"]},
        )
    ).json()

    bob_connection_id = invitation["connection_id"]
    alice_connection_id = invitation_response["connection_id"]

    # fetch and validate
    # both connections should be active - we have waited long enough for events to be exchanged
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        filter_map={"state": "completed"},
        lookback_time=5,
    )
    assert await check_webhook_state(
        bob_member_client,
        topic="connections",
        filter_map={"state": "completed"},
        lookback_time=5,
    )

    return BobAliceConnect(
        alice_connection_id=alice_connection_id, bob_connection_id=bob_connection_id
    )


@dataclass
class AcmeAliceConnect:
    alice_connection_id: str
    acme_connection_id: str


@pytest.fixture(scope="function")
async def acme_and_alice_connection(
    request,
    alice_member_client: RichAsyncClient,
    alice_tenant: CreateTenantResponse,
    acme_client: RichAsyncClient,
    acme_verifier: CreateTenantResponse,
) -> AcmeAliceConnect:
    if hasattr(request, "param") and request.param == "trust_registry":
        acme_actor = await fetch_actor_by_id(acme_verifier.wallet_id)
        assert acme_actor["didcomm_invitation"]

        invitation = acme_actor["didcomm_invitation"]
        invitation_json = base64_to_json(invitation.split("?oob=")[1])

        # accept invitation on alice side
        invitation_response = (
            await alice_member_client.post(
                f"{OOB_BASE_PATH}/accept-invitation",
                json={"invitation": invitation_json},
            )
        ).json()

        acme_listener = SseListener(
            topic="connections", wallet_id=acme_verifier.wallet_id
        )

        alice_label = alice_tenant.wallet_label
        payload = await acme_listener.wait_for_event(
            field="their_label", field_id=alice_label, desired_state="completed"
        )

        alice_connection_id = invitation_response["connection_id"]
        acme_connection_id = payload["connection_id"]
    else:
        # create invitation on acme side
        invitation = (
            await acme_client.post(f"{CONNECTIONS_BASE_PATH}/create-invitation")
        ).json()

        # accept invitation on alice side
        invitation_response = (
            await alice_member_client.post(
                f"{CONNECTIONS_BASE_PATH}/accept-invitation",
                json={"invitation": invitation["invitation"]},
            )
        ).json()

        alice_connection_id = invitation_response["connection_id"]
        acme_connection_id = invitation["connection_id"]

    # fetch and validate - both connections should be active before continuing
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": alice_connection_id},
        lookback_time=5,
    )
    assert await check_webhook_state(
        acme_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": acme_connection_id},
        lookback_time=5,
    )

    return AcmeAliceConnect(
        alice_connection_id=alice_connection_id,
        acme_connection_id=acme_connection_id,
    )


@dataclass
class FaberAliceConnect:
    alice_connection_id: str
    faber_connection_id: str


@pytest.fixture(scope="function")
async def faber_and_alice_connection(
    alice_member_client: RichAsyncClient, faber_client: RichAsyncClient
) -> FaberAliceConnect:
    # create invitation on faber side
    invitation = (
        await faber_client.post(f"{CONNECTIONS_BASE_PATH}/create-invitation")
    ).json()

    # accept invitation on alice side
    invitation_response = (
        await alice_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/accept-invitation",
            json={"invitation": invitation["invitation"]},
        )
    ).json()

    faber_connection_id = invitation["connection_id"]
    alice_connection_id = invitation_response["connection_id"]

    # fetch and validate
    # both connections should be active - we have waited long enough for events to be exchanged
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": alice_connection_id},
        lookback_time=5,
    )
    assert await check_webhook_state(
        faber_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": faber_connection_id},
        lookback_time=5,
    )

    return FaberAliceConnect(
        alice_connection_id=alice_connection_id, faber_connection_id=faber_connection_id
    )


@dataclass
class MeldCoAliceConnect:
    alice_connection_id: str
    meld_co_connection_id: str


# Create fixture to handle parameters and return either meldco-alice connection fixture
@pytest.fixture(scope="function")
async def meld_co_and_alice_connection(
    request,
    alice_tenant: CreateTenantResponse,
    alice_member_client: RichAsyncClient,
    meld_co_client: RichAsyncClient,
    meld_co_issuer_verifier: CreateTenantResponse,
) -> MeldCoAliceConnect:
    if hasattr(request, "param") and request.param == "trust_registry":
        # get invitation as on trust registry
        meldco_label = meld_co_issuer_verifier.wallet_label

        actor_record = await actors.fetch_actor_by_name(meldco_label)

        invitation = actor_record["didcomm_invitation"]
        invitation_json = base64_to_json(invitation.split("?oob=")[1])

        # accept invitation on alice side
        invitation_response = (
            await alice_member_client.post(
                f"{OOB_BASE_PATH}/accept-invitation",
                json={"invitation": invitation_json},
            )
        ).json()

        meld_co_listener = SseListener(
            topic="connections", wallet_id=meld_co_issuer_verifier.wallet_id
        )
        alice_label = alice_tenant.wallet_label
        payload = await meld_co_listener.wait_for_event(
            field="their_label", field_id=alice_label, desired_state="completed"
        )

        meld_co_connection_id = payload["connection_id"]
        alice_connection_id = invitation_response["connection_id"]
    else:
        # create invitation on meld_co side
        invitation = (
            await meld_co_client.post(f"{CONNECTIONS_BASE_PATH}/create-invitation")
        ).json()

        # accept invitation on alice side
        invitation_response = (
            await alice_member_client.post(
                f"{CONNECTIONS_BASE_PATH}/accept-invitation",
                json={"invitation": invitation["invitation"]},
            )
        ).json()

        meld_co_connection_id = invitation["connection_id"]
        alice_connection_id = invitation_response["connection_id"]

    # fetch and validate - both connections should be active before continuing
    assert await check_webhook_state(
        alice_member_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": alice_connection_id},
        lookback_time=5,
    )
    assert await check_webhook_state(
        meld_co_client,
        topic="connections",
        filter_map={"state": "completed", "connection_id": meld_co_connection_id},
        lookback_time=5,
    )

    return MeldCoAliceConnect(
        alice_connection_id=alice_connection_id,
        meld_co_connection_id=meld_co_connection_id,
    )


@dataclass
class BobAlicePublicDid:
    alice_public_did: str
    bob_public_did: str


@pytest.fixture(scope="function")
async def bob_and_alice_public_did(
    alice_acapy_client: AcaPyClient,
    bob_acapy_client: AcaPyClient,
) -> BobAlicePublicDid:
    bob_records = await bob_acapy_client.connection.get_connections()
    alice_records = await alice_acapy_client.connection.get_connections()

    await bob_acapy_client.connection.accept_invitation(
        conn_id=bob_records.results[-1].connection_id
    )
    await alice_acapy_client.connection.accept_invitation(
        conn_id=alice_records.results[-1].connection_id
    )

    bob_records = await bob_acapy_client.connection.get_connections()
    alice_records = await alice_acapy_client.connection.get_connections()

    bob_did = await create_public_did(bob_acapy_client)
    alice_did = await create_public_did(alice_acapy_client)

    if not bob_did.did or not alice_did.did:
        raise Exception("Missing public did for alice or bob")

    return BobAlicePublicDid(alice_public_did=alice_did, bob_public_did=bob_did)


class InvitationResultDict(TypedDict):
    invitation: Dict[str, Any]
    connection_id: str


class MultiInvite(TypedDict):
    multi_use_invitation: InvitationResultDict
    invitation_key: str
    did_from_rec_key: str


async def bob_multi_use_invitation(
    bob_member_client: RichAsyncClient,
) -> MultiInvite:
    create_invite_json = CreateInvitation(
        alias=None,
        multi_use=True,
        use_public_did=False,
    ).model_dump()
    # Create a multi-use invitation
    invitation = (
        await bob_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/create-invitation",
            json=create_invite_json,
        )
    ).json()

    recipient_key = invitation["invitation"]["recipientKeys"][0]
    bob_multi_invite = MultiInvite(
        multi_use_invitation=invitation,
        invitation_key=recipient_key,
        did_from_rec_key=ed25519_verkey_to_did_key(key=recipient_key),
    )

    return bob_multi_invite


@pytest.fixture(scope="function")
async def alice_bob_connect_multi(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
) -> BobAliceConnect:
    multi_use_invite = bob_multi_use_invitation(bob_member_client)
    invitation = multi_use_invite["multi_use_invitation"]["invitation"]

    # accept invitation on alice side
    invitation_response = (
        await alice_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/accept-invitation",
            json={"invitation": invitation},
        )
    ).json()

    assert await check_webhook_state(
        client=alice_member_client,
        filter_map={"state": "request-sent"},
        topic="connections",
    )

    bob_connection_id = multi_use_invite["multi_use_invitation"]["connection_id"]
    alice_connection_id = invitation_response["connection_id"]

    # fetch and validate
    # both connections should be active - we have waited long enough for events to be exchanged
    bob_connection_records = (await bob_member_client.get(CONNECTIONS_BASE_PATH)).json()

    bob_connection_id = bob_connection_records[0]["connection_id"]

    assert await check_webhook_state(
        client=alice_member_client,
        filter_map={"state": "completed"},
        topic="connections",
        lookback_time=5,
    )
    assert await check_webhook_state(
        client=bob_member_client,
        filter_map={"state": "completed"},
        topic="connections",
        lookback_time=5,
    )

    return BobAliceConnect(
        alice_connection_id=alice_connection_id, bob_connection_id=bob_connection_id
    )
