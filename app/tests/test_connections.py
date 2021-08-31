import json
import random
import string
import time
from contextlib import asynccontextmanager

from assertpy import assert_that

import dependencies
import pytest
from generic.connections import (
    accept_invite,
    create_invite,
    delete_connection_by_id,
    get_connection_by_id,
    get_connections,
)

APPLICATION_JSON_CONTENT_TYPE = {"content-type": "application/json"}

BASE_PATH = "/generic/connections"

CREATE_WALLET_PAYLOAD_YODA = {
    "image_url": "https://aries.ca/images/sample.png",
    "key_management_mode": "managed",
    "label": "YOMA",
    "wallet_dispatch_type": "default",
    "wallet_key": "MySecretKey1234",
    "wallet_name": "YodaJediPokerFunds",
    "wallet_type": "indy",
}
CREATE_WALLET_PAYLOAD_HAN = {
    "image_url": "https://aries.ca/images/sample.png",
    "key_management_mode": "managed",
    "label": "YOMA",
    "wallet_dispatch_type": "default",
    "wallet_key": "MySecretKey1234",
    "wallet_name": "HanSolosCocktailFunds",
    "wallet_type": "indy",
}


async def remove_wallets(yoda_wallet_id, han_wallet_id, async_client):
    yoda_response = await async_client.delete(
        f"/admin/wallet-multitenant/{yoda_wallet_id}",
        headers={"x-api-key": "adminApiKey", "x-role": "member"},
    )
    han_response = await async_client.delete(
        f"/admin/wallet-multitenant/{han_wallet_id}",
        headers={"x-api-key": "adminApiKey", "x-role": "member"},
    )
    return yoda_response, han_response


async def invite_creation(async_client, token, wallet_id):
    invite_creation_response = await async_client.get(
        "/generic/connections/create-invite",
        headers={
            "x-auth": f"Bearer {token}",
            "x-wallet-id": wallet_id,
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
    )
    return invite_creation_response.json()["invitation"]


async def token_responses(async_client, create_wallets_mock):
    yoda, han = create_wallets_mock

    yoda_wallet_id = yoda["wallet_id"]
    han_wallet_id = han["wallet_id"]

    yoda_token_response = await async_client.get(
        f"/admin/wallet-multitenant/{yoda_wallet_id}/auth-token",
        headers={
            "x-api-key": "adminApiKey",
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
    )

    han_token_response = await async_client.get(
        f"/admin/wallet-multitenant/{han_wallet_id}/auth-token",
        headers={
            "x-api-key": "adminApiKey",
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
    )
    yoda_token = yoda_token_response.json()["token"]
    han_token = han_token_response.json()["token"]
    return yoda_token, yoda_wallet_id, han_token, han_wallet_id


@pytest.fixture(name="create_wallets_mock")
async def fixture_create_wallets_mock(async_client):
    # Create two wallets
    gen_random_length = 42
    CREATE_WALLET_PAYLOAD_HAN["wallet_name"] = "".join(
        random.choice(string.ascii_uppercase + string.digits)  # NOSONAR # nolint
        for _ in range(gen_random_length)  # NOSONAR # nolint
    )
    CREATE_WALLET_PAYLOAD_YODA["wallet_name"] = "".join(
        random.choice(string.ascii_uppercase + string.digits)  # NOSONAR # nolint
        for _ in range(gen_random_length)  # NOSONAR # nolint
    )

    yoda_wallet_response = await async_client.post(
        "/admin/wallet-multitenant/create-wallet",
        headers={
            "x-api-key": "adminApiKey",
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
        data=json.dumps(CREATE_WALLET_PAYLOAD_YODA),
    )
    yoda_wallet_response = yoda_wallet_response.json()
    yoda_wallet_id = yoda_wallet_response["wallet_id"]
    han_wallet_response = await async_client.post(
        "/admin/wallet-multitenant/create-wallet",
        headers={
            "x-api-key": "adminApiKey",
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
        data=json.dumps(CREATE_WALLET_PAYLOAD_HAN),
    )
    han_wallet_response = han_wallet_response.json()
    han_wallet_id = han_wallet_response["wallet_id"]
    yield yoda_wallet_response, han_wallet_response

    yoda_response, han_response = await remove_wallets(
        yoda_wallet_id, han_wallet_id, async_client
    )
    assert yoda_response.status_code == 200
    assert yoda_response.json() == {"status": "Successfully removed wallet"}
    assert han_response.status_code == 200
    assert han_response.json() == {"status": "Successfully removed wallet"}


@pytest.mark.asyncio
async def test_create_invite(async_client, create_wallets_mock):
    yoda, _ = create_wallets_mock

    yoda_wallet_id = yoda["wallet_id"]

    yoda_token_response = await async_client.get(
        f"/admin/wallet-multitenant/{yoda_wallet_id}/auth-token",
        headers={
            "x-api-key": "adminApiKey",
            "x-role": "member",
            **APPLICATION_JSON_CONTENT_TYPE,
        },
    )

    yoda_token = yoda_token_response.json()["token"]

    async with asynccontextmanager(dependencies.member_agent)(
        x_auth=f"Bearer {yoda_token}", x_wallet_id=yoda_wallet_id
    ) as member_agent:
        invite_creation_response = await create_invite(member_agent)
    assert (
        invite_creation_response["connection_id"]
        and invite_creation_response["connection_id"] != {}
    )
    assert (
        invite_creation_response["invitation"]
        and invite_creation_response["invitation"] != {}
    )
    assert (
        invite_creation_response["invitation"]["@id"]
        and invite_creation_response["invitation"]["@id"] != {}
    )


@pytest.mark.asyncio
async def test_accept_invite(async_client, create_wallets_mock):
    yoda_token, yoda_wallet_id, han_token, han_wallet_id = await token_responses(
        async_client, create_wallets_mock
    )

    invite = await invite_creation(async_client, yoda_token, yoda_wallet_id)

    async with asynccontextmanager(dependencies.member_agent)(
        x_auth=f"Bearer {han_token}", x_wallet_id=han_wallet_id
    ) as member_agent:
        accept_invite_response = await accept_invite(
            invite=invite, aries_controller=member_agent
        )
    assert (
        accept_invite_response["accept"] and accept_invite_response["accept"] == "auto"
    )
    assert (
        accept_invite_response["created_at"]
        and accept_invite_response["created_at"] != ""
    )
    assert (
        accept_invite_response["invitation_key"]
        and accept_invite_response["invitation_key"] != ""
    )


@pytest.mark.asyncio
async def test_get_connections(async_client, create_wallets_mock):
    yoda_token, yoda_wallet_id, han_token, han_wallet_id = await token_responses(
        async_client, create_wallets_mock
    )

    invite = await invite_creation(async_client, yoda_token, yoda_wallet_id)

    async with asynccontextmanager(dependencies.member_agent)(
        x_auth=f"Bearer {han_token}", x_wallet_id=han_wallet_id
    ) as member_agent:
        await accept_invite(invite=invite, aries_controller=member_agent)
        connection = await get_connections(aries_controller=member_agent)

    assert connection["results"] and len(connection["results"]) >= 1
    assert (
        connection["results"][0]["accept"]
        and connection["results"][0]["accept"] == "auto"
    )
    assert (
        connection["results"][0]["connection_id"]
        and connection["results"][0]["connection_id"] != ""
    )
    assert (
        connection["results"][0]["created_at"]
        and connection["results"][0]["created_at"] != ""
    )
    assert (
        connection["results"][0]["invitation_key"]
        and connection["results"][0]["invitation_key"] != ""
    )


@pytest.mark.asyncio
async def test_get_connection_by_id(async_client, create_wallets_mock):
    yoda_token, yoda_wallet_id, han_token, han_wallet_id = await token_responses(
        async_client, create_wallets_mock
    )

    invite = await invite_creation(async_client, yoda_token, yoda_wallet_id)

    async with asynccontextmanager(dependencies.member_agent)(
        x_auth=f"Bearer {han_token}", x_wallet_id=han_wallet_id
    ) as member_agent:
        await accept_invite(invite=invite, aries_controller=member_agent)
        connection = await get_connections(aries_controller=member_agent)
        connection_id = connection["results"][0]["connection_id"]
        connection_from_method = await get_connection_by_id(
            connection_id=connection_id, aries_controller=member_agent
        )
    assert connection["results"][0] == connection_from_method


@pytest.mark.asyncio
async def test_delete_connection(async_client, create_wallets_mock):
    yoda_token, yoda_wallet_id, han_token, han_wallet_id = await token_responses(
        async_client, create_wallets_mock
    )

    invite = await invite_creation(async_client, yoda_token, yoda_wallet_id)

    async with asynccontextmanager(dependencies.member_agent)(
        x_auth=f"Bearer {han_token}", x_wallet_id=han_wallet_id
    ) as member_agent:
        await accept_invite(invite=invite, aries_controller=member_agent)
        connection = await get_connections(aries_controller=member_agent)
        connection_id = connection["results"][0]["connection_id"]
        await delete_connection_by_id(
            connection_id=connection_id, aries_controller=member_agent
        )
        connection = await get_connections(aries_controller=member_agent)
    assert connection["results"] == []


@pytest.mark.asyncio
async def test_bob_and_alice_connect(async_client_bob, async_client_alice):
    """this test validates that bob and alice connect successfully...

    NB: it assumes you have all the "auto connection" settings flagged as on.

    ACAPY_AUTO_ACCEPT_INVITES=true
    ACAPY_AUTO_ACCEPT_REQUESTS=true
    ACAPY_AUTO_PING_CONNECTION=true

    """
    # create invitation on bob side
    invitation = (await async_client_bob.get(BASE_PATH + "/create-invite")).json()
    bob_connection_id = invitation["connection_id"]
    connections = (await async_client_bob.get(BASE_PATH)).json()
    assert_that(connections["results"]).extracting("connection_id").contains_only(
        bob_connection_id
    )

    # accept invitation on alice side
    invite_response = (
        await async_client_alice.post(
            BASE_PATH + "/accept-invite", data=json.dumps(invitation["invitation"])
        )
    ).json()
    alice_connection_id = invite_response["connection_id"]

    # wait for events to be exchanged
    time.sleep(10)

    # fetch and validate
    # both connections should be active - we have waited long enough for events to be exchanged
    # and we are running in "auto connect" mode.
    bob_connections = (await async_client_bob.get(BASE_PATH)).json()
    alice_connections = (await async_client_alice.get(BASE_PATH)).json()

    assert_that(bob_connections["results"]).extracting("connection_id").contains(
        bob_connection_id
    )
    bob_connection = [
        c for c in bob_connections["results"] if c["connection_id"] == bob_connection_id
    ][0]
    assert_that(bob_connection).has_state("active")

    assert_that(alice_connections["results"]).extracting("connection_id").contains(
        alice_connection_id
    )
    alice_connection = [
        c
        for c in alice_connections["results"]
        if c["connection_id"] == alice_connection_id
    ][0]
    assert_that(alice_connection).has_state("active")


@pytest.mark.asyncio
async def test_bob_has_agent(async_client_bob):
    assert_that(hasattr(async_client_bob, "agent")).is_true()
    assert_that(hasattr(async_client_bob.agent, "did")).is_true()
    assert_that(async_client_bob.agent.did).is_not_none()
    assert_that(async_client_bob.agent.headers).is_not_empty()
    assert_that(async_client_bob.agent.token).is_not_none()
