import asyncio

import pytest
from aries_cloudcontroller import AcaPyClient
from fastapi import HTTPException

from app.routes.admin.tenants import router as tenants_router
from app.routes.connections import router as connections_router
from app.services import acapy_wallet
from app.tests.util.webhooks import check_webhook_state, get_wallet_id_from_async_client
from shared import RichAsyncClient

CONNECTIONS_BASE_PATH = connections_router.prefix
TENANTS_BASE_PATH = tenants_router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize(
    "use_did,use_did_method,use_public_did",
    [
        (None, None, False),
        (True, None, False),
        (None, "did:peer:2", False),
        (None, "did:peer:4", False),
        (True, "did:peer:4", False),
        (None, None, True),
    ],
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_create_did_exchange_request(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    alice_acapy_client: AcaPyClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    use_did: str | None,
    use_did_method: str | None,
    use_public_did: bool,
):
    faber_public_did = await acapy_wallet.get_public_did(
        controller=faber_anoncreds_acapy_client
    )

    request_data = {"their_public_did": faber_public_did.did}

    if use_did:
        new_did = await acapy_wallet.create_did(controller=alice_acapy_client)
        request_data["use_did"] = new_did.did

    if use_did_method:
        request_data["use_did_method"] = use_did_method

    if use_public_did:
        request_data["use_public_did"] = use_public_did

    if use_public_did:  # Alice doesn't have a public DID
        with pytest.raises(HTTPException) as exc_info:
            response = await alice_member_client.post(
                f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request",
                params=request_data,
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == """{"detail":"No public DID configured."}"""

    elif use_did and use_did_method:
        with pytest.raises(HTTPException) as exc_info:
            await alice_member_client.post(
                f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request",
                params=request_data,
            )
        assert exc_info.value.status_code == 400
        assert (
            exc_info.value.detail
            == """{"detail":"Cannot specify both use_did and use_did_method."}"""
        )
    else:
        response = await alice_member_client.post(
            f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request", params=request_data
        )
        assert response.status_code == 200
        connection_record = response.json()
        assert connection_record["connection_id"]
        assert connection_record["state"] == "request-sent"

        alice_connection_id = connection_record["connection_id"]
        alice_did = connection_record["my_did"]

        try:
            # Due to auto-accepts, Alice's connection is complete
            assert await check_webhook_state(
                alice_member_client,
                topic="connections",
                state="completed",
                filter_map={"connection_id": alice_connection_id},
            )
            # Faber now has a complete connection too
            assert await check_webhook_state(
                faber_anoncreds_client,
                topic="connections",
                state="completed",
                filter_map={"their_did": alice_did},
            )
        finally:
            await asyncio.sleep(1)  # Short sleep assists in avoiding 500 error
            # Delete connection records:
            await alice_member_client.delete(
                f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}"
            )


@pytest.mark.anyio
@pytest.mark.skip(
    "Changing Faber wallet settings during xdist run can break other tests. "
    "This test works in isolation. Should be refactored to run in parallel."
)
@pytest.mark.parametrize("use_public_did", [False])
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_accept_did_exchange_invitation(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    tenant_admin_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    use_public_did: bool,
):
    # First disable auto-accept invites for Faber
    faber_wallet_id = get_wallet_id_from_async_client(client=faber_anoncreds_client)
    await tenant_admin_client.put(
        f"{TENANTS_BASE_PATH}/{faber_wallet_id}",
        json={"extra_settings": {"ACAPY_AUTO_ACCEPT_REQUESTS": False}},
    )

    faber_public_did = await acapy_wallet.get_public_did(
        controller=faber_anoncreds_acapy_client
    )

    request_data = {"their_public_did": faber_public_did.did}

    alice_create_request_response = await alice_member_client.post(
        f"{CONNECTIONS_BASE_PATH}/did-exchange/create-request", params=request_data
    )
    alice_create_request_response = alice_create_request_response.json()

    alice_connection_id = alice_create_request_response["connection_id"]
    alice_did = alice_create_request_response["my_did"]

    try:
        faber_connection_request_received_event = await check_webhook_state(
            faber_anoncreds_client,
            topic="connections",
            state="request-received",
            filter_map={"their_did": alice_did},
        )

        faber_connection_id = faber_connection_request_received_event["connection_id"]

        accept_params = {
            "connection_id": faber_connection_id,
            "use_public_did": use_public_did,
        }

        faber_accept_request_response = await faber_anoncreds_client.post(
            f"{CONNECTIONS_BASE_PATH}/did-exchange/accept-request", params=accept_params
        )
        assert faber_accept_request_response.status_code == 200
        accept_response = faber_accept_request_response.json()
        assert accept_response["state"] == "response-sent"

        # Now Alice's connection is complete
        assert await check_webhook_state(
            alice_member_client,
            topic="connections",
            state="completed",
            filter_map={"connection_id": alice_connection_id},
        )

        # And Faber's connection is complete
        assert await check_webhook_state(
            faber_anoncreds_client,
            topic="connections",
            state="completed",
            filter_map={"connection_id": faber_connection_id},
        )
    finally:
        await asyncio.sleep(1)  # Short sleep assists in avoiding 500 error
        # Delete connection records:
        await alice_member_client.delete(
            f"{CONNECTIONS_BASE_PATH}/{alice_connection_id}"
        )

        # Reconfigure ACAPY_AUTO_ACCEPT_REQUESTS for Faber
        await tenant_admin_client.put(
            f"{TENANTS_BASE_PATH}/{faber_wallet_id}",
            json={"extra_settings": {"ACAPY_AUTO_ACCEPT_REQUESTS": True}},
        )
