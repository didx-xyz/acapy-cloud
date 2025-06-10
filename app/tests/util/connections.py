from dataclasses import dataclass

from app.models.tenants import CreateTenantResponse
from app.routes.connections import router as conn_router
from app.routes.oob import router as oob_router
from app.routes.wallet.dids import router as did_router
from app.services.trust_registry.actors import fetch_actor_by_id
from app.tests.util.regression_testing import (
    RegressionTestConfig,
    TestMode,
    assert_fail_on_recreating_fixtures,
)
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from app.util.did import qualified_did_sov
from app.util.string import base64_to_json
from shared import RichAsyncClient
from shared.models.connection_record import Connection

OOB_BASE_PATH = oob_router.prefix
CONNECTIONS_BASE_PATH = conn_router.prefix
DID_BASE_PATH = did_router.prefix


@dataclass
class BobAliceConnect:
    alice_connection_id: str
    bob_connection_id: str


@dataclass
class AcmeAliceConnect:
    alice_connection_id: str
    acme_connection_id: str


@dataclass
class FaberAliceConnect:
    alice_connection_id: str
    faber_connection_id: str


@dataclass
class MeldCoAliceConnect:
    alice_connection_id: str
    meld_co_connection_id: str


async def assert_both_connections_ready(
    member_client_1: RichAsyncClient,
    member_client_2: RichAsyncClient,
    connection_id_1: str,
    connection_id_2: str,
) -> None:
    await assert_both_webhooks_received(
        member_client_1,
        member_client_2,
        topic="connections",
        state="completed",
        field_id_1=connection_id_1,
        field_id_2=connection_id_2,
    )


async def create_bob_alice_connection(
    alice_member_client: RichAsyncClient, bob_member_client: RichAsyncClient, alias: str
):
    # Bob create invitation
    bob_invitation = (
        await bob_member_client.post(
            f"{OOB_BASE_PATH}/create-invitation",
            json={
                "alias": alias,
                "multi_use": False,
                "use_public_did": False,
                "create_connection": True,
            },
        )
    ).json()

    # Alice accept invitation
    alice_oob_response = (
        await alice_member_client.post(
            f"{OOB_BASE_PATH}/accept-invitation",
            json={"alias": alias, "invitation": bob_invitation["invitation"]},
        )
    ).json()

    # Get connection details
    alice_connection = await check_webhook_state(
        client=alice_member_client,
        topic="connections",
        state="completed",
        filter_map={"connection_id": alice_oob_response["connection_id"]},
    )

    # Use Alice's connection DID to fetch Bob's connection
    msg_id = alice_connection["invitation_msg_id"]

    bob_connection = await check_webhook_state(
        client=bob_member_client,
        topic="connections",
        state="completed",
        filter_map={"invitation_msg_id": msg_id},
    )

    bob_connection_id = bob_connection["connection_id"]
    alice_connection_id = alice_connection["connection_id"]

    return BobAliceConnect(
        alice_connection_id=alice_connection_id, bob_connection_id=bob_connection_id
    )


async def fetch_existing_connection_by_alias(
    member_client: RichAsyncClient,
    alias: str | None = None,
    their_label: str | None = None,
    their_did: str | None = None,
) -> Connection | None:
    params = {"state": "completed", "limit": 10000}
    if alias:
        params.update({"alias": alias})
    if their_did:
        params.update({"their_did": their_did})

    list_connections_response = await member_client.get(
        CONNECTIONS_BASE_PATH, params=params
    )
    list_connections = list_connections_response.json()

    if their_label:  #  to handle Trust Registry invites, where alias is null
        list_connections = [
            connection
            for connection in list_connections
            if (
                connection["their_label"] == their_label  # filter by their label
                and connection["alias"] is None  # TR OOB invite has null alias
            )
        ]

    num_connections = len(list_connections)
    assert num_connections < 2, (
        f"{member_client.name} should have 1 or 0 connections, got: {num_connections}"
    )

    if list_connections:
        return Connection.model_validate(list_connections[0])


async def fetch_or_create_connection(
    alice_member_client: RichAsyncClient,
    bob_member_client: RichAsyncClient,
    connection_alias: str,
) -> BobAliceConnect:
    # fetch connection with this alias for both bob and alice
    alice_connection = await fetch_existing_connection_by_alias(
        alice_member_client, connection_alias
    )

    their_did = alice_connection.my_did if alice_connection else None

    bob_connection = await fetch_existing_connection_by_alias(
        member_client=bob_member_client,
        alias=connection_alias if not their_did else None,
        their_did=their_did,
    )

    # Check if connections exist
    if alice_connection and bob_connection:
        return BobAliceConnect(
            alice_connection_id=alice_connection.connection_id,
            bob_connection_id=bob_connection.connection_id,
        )
    else:
        # Create connection since they don't exist
        assert_fail_on_recreating_fixtures()
        return await create_bob_alice_connection(
            bob_member_client=bob_member_client,
            alice_member_client=alice_member_client,
            alias=connection_alias,
        )


async def create_connection_by_test_mode(
    test_mode: str,
    alice_member_client: RichAsyncClient,
    bob_member_client: RichAsyncClient,
    alias: str,
) -> BobAliceConnect:
    if test_mode == TestMode.clean_run:
        return await create_bob_alice_connection(
            bob_member_client=bob_member_client,
            alice_member_client=alice_member_client,
            alias=alias,
        )
    elif test_mode == TestMode.regression_run:
        connection_alias_prefix = RegressionTestConfig.reused_connection_alias

        return await fetch_or_create_connection(
            alice_member_client,
            bob_member_client,
            connection_alias=f"{connection_alias_prefix}-{alias}",
        )
    else:
        assert False, f"unknown test mode: {test_mode}"


async def connect_using_trust_registry_invite(
    alice_member_client: RichAsyncClient,
    alice_tenant: CreateTenantResponse,
    actor_client: RichAsyncClient,
    actor: CreateTenantResponse,
    connection_alias: str,
) -> BobAliceConnect:
    fetched_actor = await fetch_actor_by_id(actor.wallet_id)
    assert fetched_actor.didcomm_invitation

    invitation = fetched_actor.didcomm_invitation
    invitation_json = base64_to_json(invitation.split("?oob=")[1])

    # accept invitation on alice side -- she uses here connection alias
    invitation_response = (
        await alice_member_client.post(
            f"{OOB_BASE_PATH}/accept-invitation",
            json={"alias": connection_alias, "invitation": invitation_json},
        )
    ).json()

    alice_label = alice_tenant.wallet_label
    payload = await check_webhook_state(
        client=actor_client,
        topic="connections",
        state="completed",
        filter_map={
            "their_label": alice_label,
        },
    )

    alice_connection_id = invitation_response["connection_id"]
    actor_connection_id = payload["connection_id"]

    # both connections should be active before continuing
    await assert_both_connections_ready(
        alice_member_client, actor_client, alice_connection_id, actor_connection_id
    )

    return BobAliceConnect(
        alice_connection_id=alice_connection_id, bob_connection_id=actor_connection_id
    )


async def fetch_or_create_trust_registry_connection(
    alice_member_client: RichAsyncClient,
    alice_tenant: CreateTenantResponse,
    actor_client: RichAsyncClient,
    actor: CreateTenantResponse,
    connection_alias: str,
) -> BobAliceConnect:
    # fetch connection by alias for alice's side
    alice_connection = await fetch_existing_connection_by_alias(
        alice_member_client, alias=connection_alias
    )
    their_did = alice_connection.my_did if alice_connection else None
    actor_connection = await fetch_existing_connection_by_alias(
        actor_client,
        alias=None,
        their_label=alice_tenant.wallet_label,
        their_did=their_did,
    )

    # Check if connections exist
    if alice_connection and actor_connection:
        return BobAliceConnect(
            alice_connection_id=alice_connection.connection_id,
            bob_connection_id=actor_connection.connection_id,
        )
    else:
        assert not alice_connection, "Alice has connection, but not found for actor"
        assert not actor_connection, "Actor has connection, but not for Alice"

        # Create connection since they don't exist
        assert_fail_on_recreating_fixtures()
        return await connect_using_trust_registry_invite(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            actor_client=actor_client,
            actor=actor,
            connection_alias=connection_alias,
        )


async def create_did_exchange_w_public_did(
    bob_member_client: RichAsyncClient, alice_member_client: RichAsyncClient, alias: str
) -> BobAliceConnect:
    # Get Bob's public DID. Bob is the issuer in this case i.e. should have public DID
    did_response = (await bob_member_client.get(f"{DID_BASE_PATH}/public")).json()

    bob_public_did = qualified_did_sov(did_response["did"])

    # Alice create invitation
    alice_connection = (
        await alice_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request",
            params={
                "their_public_did": bob_public_did,
                "alias": alias,
            },
        )
    ).json()

    alice_label = alice_member_client.name[7:-7]
    bob_connection = await check_webhook_state(
        client=bob_member_client,
        topic="connections",
        state="request-received",
        filter_map={"their_label": alice_label},
    )

    bob_connection_id = bob_connection["connection_id"]
    alice_connection_id = alice_connection["connection_id"]

    # validate both connections should be active
    await assert_both_connections_ready(
        alice_member_client, bob_member_client, alice_connection_id, bob_connection_id
    )

    return BobAliceConnect(
        alice_connection_id=alice_connection_id, bob_connection_id=bob_connection_id
    )
