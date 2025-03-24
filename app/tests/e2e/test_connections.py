import asyncio
from typing import List, Optional

import pytest
from fastapi import HTTPException

from app.models.connections import AcceptInvitation, CreateInvitation
from app.routes.connections import router
from app.tests.util.connections import BobAliceConnect, create_bob_alice_connection
from app.tests.util.regression_testing import TestMode
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient

CONNECTIONS_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize(
    "alias,multi_use,use_public_did",
    [
        (None, False, False),
        ("alias", False, False),
        ("alias", True, False),
        ("alias", False, True),
        ("alias", True, True),
    ],
)
async def test_create_invitation_no_public_did(
    bob_member_client: RichAsyncClient,  # bob has no public did
    alias: Optional[str],
    multi_use: bool,
    use_public_did: bool,
):
    invite_json = CreateInvitation(
        alias=alias, multi_use=multi_use, use_public_did=use_public_did
    ).model_dump()

    if use_public_did:
        with pytest.raises(HTTPException) as exc_info:
            # regular holders cannot `use_public_did` as they do not have a public did
            await bob_member_client.post(
                f"{CONNECTIONS_BASE_PATH}/create-invitation", json=invite_json
            )
        assert exc_info.value.status_code == 400
        assert (
            exc_info.value.detail
            == """{"detail":"Cannot create public invitation with no public DID."}"""
        )
    else:
        response = await bob_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/create-invitation", json=invite_json
        )
        assert response.status_code == 200

        invitation = response.json()

        assert invitation["connection_id"] is not None
        assert isinstance(invitation["invitation"], dict)
        for key in ["@id", "@type", "recipientKeys", "serviceEndpoint"]:
            assert key in invitation["invitation"]
        assert invitation["invitation_url"].startswith("https://")


expected_keys = ("connection_id", "state", "created_at", "updated_at", "invitation_key")


@pytest.mark.anyio
async def test_accept_invitation(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    alias = "test_alias"
    invitation_response = await bob_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/create-invitation"
    )
    invitation = invitation_response.json()

    accept_invite_json = AcceptInvitation(
        alias=alias,
        invitation=invitation["invitation"],
    ).model_dump()

    accept_response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/accept-invitation",
        json=accept_invite_json,
    )
    connection_record = accept_response.json()

    for key in expected_keys:
        assert key in connection_record
    assert connection_record["state"] == "request-sent"
    assert connection_record["alias"] == alias

    assert await check_webhook_state(
        client=alice_member_client,
        topic="connections",
        state="completed",
        filter_map={
            "connection_id": connection_record["connection_id"],
        },
    )


@pytest.mark.anyio
async def test_get_connections(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    connection_alias = "TempAliceBobConnection"

    bob_and_alice_connection = await create_bob_alice_connection(
        alice_member_client, bob_member_client, alias=connection_alias
    )

    alice_connection_id = bob_and_alice_connection.alice_connection_id
    bob_connection_id = bob_and_alice_connection.bob_connection_id

    try:
        alice_connection = (
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}"
            )
        ).json()
        bob_connection = (
            await bob_member_client.get(f"{CONNECTIONS_BASE_PATH}/{bob_connection_id}")
        ).json()

        alice_invitation_msg_id_value = alice_connection["invitation_msg_id"]
        alice_did = alice_connection["my_did"]

        alice_connection_alias = (
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}?alias={connection_alias}"
            )
        ).json()[0]["alias"]
        assert alice_connection_alias == connection_alias

        alice_state = (
            await alice_member_client.get(f"{CONNECTIONS_BASE_PATH}?state=completed")
        ).json()[0]["state"]
        assert alice_state == "completed"

        alice_key = (
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}?invitation_key={bob_connection['invitation_key']}"
            )
        ).json()[0]["invitation_key"]
        assert alice_key == alice_connection["invitation_key"]

        alice_invitation_msg_id = (
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}?invitation_msg_id={alice_invitation_msg_id_value}"
            )
        ).json()[0]["invitation_msg_id"]
        assert alice_invitation_msg_id == alice_invitation_msg_id_value

        alice_my_did = (
            await alice_member_client.get(f"{CONNECTIONS_BASE_PATH}?my_did={alice_did}")
        ).json()[0]["my_did"]
        assert alice_my_did == alice_did

        alice_their_did = (
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}?their_did={bob_connection['my_did']}"
            )
        ).json()[0]["their_did"]
        assert alice_their_did == alice_connection["their_did"]

        with pytest.raises(HTTPException) as exc:
            await alice_member_client.get(
                f"{CONNECTIONS_BASE_PATH}?their_public_did={bob_connection['their_public_did']}"
            )
        assert exc.value.status_code == 422

        alice_their_role = (
            await alice_member_client.get(f"{CONNECTIONS_BASE_PATH}?their_role=inviter")
        ).json()[0]["their_role"]
        assert alice_their_role == "inviter"

    finally:
        # clean up temp connection
        await alice_member_client.delete(
            f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}"
        )


@pytest.mark.anyio
async def test_get_connection_by_id(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    connection_alias = "TempAliceBobConnectionById"

    bob_and_alice_connection = await create_bob_alice_connection(
        alice_member_client, bob_member_client, alias=connection_alias
    )

    bob_connection_id = bob_and_alice_connection.bob_connection_id
    try:
        connection_response = await bob_member_client.get(
            f"{CONNECTIONS_BASE_PATH}/{bob_connection_id}"
        )
        connection_record = connection_response.json()

        assert connection_response.status_code == 200
        for key in expected_keys:
            assert key in connection_record
        assert connection_record["alias"] == connection_alias
    finally:
        await bob_member_client.delete(f"{CONNECTIONS_BASE_PATH}/{bob_connection_id}")


@pytest.mark.anyio
async def test_delete_connection(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
):
    connection_alias = "TempAliceBobConnectionDelete"

    bob_and_alice_connection = await create_bob_alice_connection(
        alice_member_client, bob_member_client, alias=connection_alias
    )

    bob_connection_id = bob_and_alice_connection.bob_connection_id
    alice_connection_id = bob_and_alice_connection.alice_connection_id

    response = await bob_member_client.delete(
        f"{CONNECTIONS_BASE_PATH}/{bob_connection_id}"
    )
    assert response.status_code == 204

    with pytest.raises(HTTPException) as exc:
        await bob_member_client.get(f"{CONNECTIONS_BASE_PATH}/{bob_connection_id}")
    assert exc.value.status_code == 404

    # Short sleep to allow alice's records to update
    await asyncio.sleep(0.5)

    # Check that the connection is deleted for alice as well
    with pytest.raises(HTTPException) as exc:
        await alice_member_client.get(f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}")
    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Skip pagination tests in regression mode",
)
async def test_get_connections_paginated(
    bob_member_client: RichAsyncClient, alice_member_client: RichAsyncClient
):
    num_connections_to_test = 5
    test_alias = "test_pagination"

    bob_alice_connections: List[BobAliceConnect] = []
    try:
        for _ in range(num_connections_to_test):
            bob_and_alice_connection = await create_bob_alice_connection(
                alice_member_client, bob_member_client, alias=test_alias
            )
            bob_alice_connections += (bob_and_alice_connection,)

        # Test different limits
        for limit in range(1, num_connections_to_test + 2):
            num_tries = 0
            retry = True
            while retry and num_tries < 5:  # Handle case where record doesn't exist yet
                response = await alice_member_client.get(
                    CONNECTIONS_BASE_PATH,
                    params={
                        "alias": test_alias,
                        "limit": limit,
                    },
                )

                connections = response.json()
                expected_num = min(limit, num_connections_to_test)
                if len(connections) != expected_num:
                    num_tries += 1
                    await asyncio.sleep(0.2)
                else:
                    retry = False
            assert (
                not retry
            ), f"Expected {expected_num} records, got {len(connections)}: {connections}"

        # Test ascending order
        response = await alice_member_client.get(
            CONNECTIONS_BASE_PATH,
            params={
                "alias": test_alias,
                "limit": num_connections_to_test,
                "descending": False,
            },
        )
        connections_asc = response.json()
        assert len(connections_asc) == num_connections_to_test

        # Verify that the connections are in ascending order based on created_at
        assert connections_asc == sorted(
            connections_asc, key=lambda x: x["created_at"], reverse=False
        )

        # Test descending order
        response = await alice_member_client.get(
            CONNECTIONS_BASE_PATH,
            params={
                "alias": test_alias,
                "limit": num_connections_to_test,
                "descending": True,
            },
        )
        connections_desc = response.json()
        assert len(connections_desc) == num_connections_to_test

        # Verify that the connections are in descending order based on created_at
        assert connections_desc == sorted(
            connections_desc, key=lambda x: x["created_at"], reverse=True
        )

        # Compare ascending and descending order results
        assert connections_desc == sorted(
            connections_asc, key=lambda x: x["created_at"], reverse=True
        )

        # Test offset greater than number of records
        response = await alice_member_client.get(
            CONNECTIONS_BASE_PATH,
            params={
                "alias": test_alias,
                "limit": 1,
                "offset": num_connections_to_test,
            },
        )
        connections = response.json()
        assert len(connections) == 0

        # Test fetching unique records with pagination
        prev_connections = []
        for offset in range(num_connections_to_test):
            response = await alice_member_client.get(
                CONNECTIONS_BASE_PATH,
                params={
                    "alias": test_alias,
                    "limit": 1,
                    "offset": offset,
                },
            )

            connections = response.json()
            assert len(connections) == 1

            record = connections[0]
            assert record not in prev_connections
            prev_connections += (record,)

        # Test invalid limit and offset values
        invalid_params = [
            {"limit": -1},  # must be positive
            {"offset": -1},  # must be positive
            {"limit": 0},  # must be greater than 0
            {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
        ]

        for params in invalid_params:
            with pytest.raises(HTTPException) as exc:
                await alice_member_client.get(CONNECTIONS_BASE_PATH, params=params)
            assert exc.value.status_code == 422

    finally:
        # Clean up connections
        for conn in bob_alice_connections:
            await alice_member_client.delete(
                f"{CONNECTIONS_BASE_PATH}/{conn.alice_connection_id}"
            )
