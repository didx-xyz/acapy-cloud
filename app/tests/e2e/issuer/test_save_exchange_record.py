import asyncio
import json
from typing import Optional

import pytest
from fastapi import HTTPException

from app.routes.issuer import router
from app.tests.fixtures.credentials import sample_credential_attributes
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.parametrize("save_exchange_record", [None, False, True])
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_issue_credential_with_save_exchange_record(
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
    save_exchange_record: Optional[bool],
) -> CredentialExchange:
    credential = {
        "type": "anoncreds",
        "connection_id": faber_anoncreds_and_alice_connection.faber_connection_id,
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id,
            "attributes": sample_credential_attributes,
        },
        "save_exchange_record": save_exchange_record,
    }

    # create and send credential offer- issuer
    faber_send_response = (
        await faber_anoncreds_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
    ).json()

    faber_credential_exchange_id = faber_send_response["credential_exchange_id"]
    thread_id = faber_send_response["thread_id"]

    try:
        payload = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        )

        alice_credential_exchange_id = payload["credential_exchange_id"]

        # send credential request - holder
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}/request",
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": alice_credential_exchange_id,
            },
        )
        await asyncio.sleep(1)  # short sleep to allow records to delete. See #957

        # faber requesting auto_remove only removes their cred ex records
        # get exchange record from alice side -- should not exist after complete
        with pytest.raises(HTTPException) as exc:
            await alice_member_client.get(
                f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}"
            )
        assert exc.value.status_code == 404

        if save_exchange_record:
            # get exchange records from faber side:
            faber_cred_ex_record = (
                await faber_anoncreds_client.get(
                    f"{CREDENTIALS_BASE_PATH}/{faber_credential_exchange_id}"
                )
            ).json()

            # Save record True, should be 1 record
            assert (
                faber_cred_ex_record["credential_exchange_id"]
                == faber_credential_exchange_id
            )
        else:
            # If save_exchange_record was not set, exchange record should not exist for Faber
            with pytest.raises(HTTPException) as exc:
                await faber_anoncreds_client.get(
                    f"{CREDENTIALS_BASE_PATH}/{faber_credential_exchange_id}"
                )
            assert exc.value.status_code == 404

    finally:
        # Clean up
        if save_exchange_record:
            await faber_anoncreds_client.delete(
                f"{CREDENTIALS_BASE_PATH}/{faber_credential_exchange_id}"
            )


@pytest.mark.anyio
@pytest.mark.parametrize("save_exchange_record", [None, False, True])
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_request_credential_with_save_exchange_record(
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
    save_exchange_record: bool,
):
    # This test asserts that the holder can control `save_exchange_records` behaviour
    credential = {
        "type": "anoncreds",
        "connection_id": faber_anoncreds_and_alice_connection.faber_connection_id,
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id,
            "attributes": {"speed": "20", "name": "Alice", "age": "44"},
        },
        "save_exchange_record": True,  # so we can safely delete faber cred ex record in finally block
    }

    # Create and send credential offer - issuer
    faber_send_response = (
        await faber_anoncreds_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
    ).json()

    faber_credential_exchange_id = faber_send_response["credential_exchange_id"]
    thread_id = faber_send_response["thread_id"]

    try:
        # Wait for holder to receive offer
        payload = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        )

        alice_credential_exchange_id = payload["credential_exchange_id"]

        # Send credential request - holder
        params = {}
        if save_exchange_record is not None:
            params = {"save_exchange_record": save_exchange_record}

        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}/request",
            params=params,
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": alice_credential_exchange_id,
            },
        )

        if save_exchange_record:
            # Get exchange record from alice side - should exist if save_exchange_record=True
            alice_cred_ex_record = (
                await alice_member_client.get(
                    f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}"
                )
            ).json()

            assert (
                alice_cred_ex_record["credential_exchange_id"]
                == alice_credential_exchange_id
            )
        else:
            # If save_exchange_record was False, credential should not exist for holder
            await asyncio.sleep(1)  # short sleep to allow records to delete. See #957
            with pytest.raises(HTTPException) as exc:
                await alice_member_client.get(
                    f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}"
                )
            assert exc.value.status_code == 404

    finally:
        # Clean up
        if save_exchange_record:
            await alice_member_client.delete(
                f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}"
            )
        await faber_anoncreds_client.delete(
            f"{CREDENTIALS_BASE_PATH}/{faber_credential_exchange_id}"
        )


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_cred_exchange_records(
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
):
    # Fetch existing records so we can filter to exclude them. Necessary to cater for long running / regression tests
    existing_records = (
        await alice_member_client.get(CREDENTIALS_BASE_PATH + "?state=offer-received")
    ).json()

    credential = {
        "type": "anoncreds",
        "connection_id": faber_anoncreds_and_alice_connection.faber_connection_id,
        "anoncreds_credential_detail": {
            "credential_definition_id": anoncreds_credential_definition_id,
            "attributes": {"speed": "20", "name": "Alice", "age": "44"},
        },
        "save_exchange_record": True,
    }

    faber_send_response_1 = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH, json=credential
    )
    faber_send_response_2 = await faber_anoncreds_client.post(
        CREDENTIALS_BASE_PATH, json=credential
    )

    faber_cred_ex_id_1 = faber_send_response_1.json()["credential_exchange_id"]
    faber_cred_ex_id_2 = faber_send_response_2.json()["credential_exchange_id"]

    faber_cred_ids = [faber_cred_ex_id_1, faber_cred_ex_id_2]

    num_tries = 0
    num_credentials_returned = 0
    while num_credentials_returned != 2 and num_tries < 10:
        await asyncio.sleep(0.25)
        alice_cred_ex_response = (
            await alice_member_client.get(
                CREDENTIALS_BASE_PATH,
                params={"state": "offer-received", "limit": 10000},
            )
        ).json()

        # Filter to only new records
        alice_cred_ex_response = [
            record
            for record in alice_cred_ex_response
            if record not in existing_records
        ]

        num_credentials_returned = len(alice_cred_ex_response)
        num_tries += 1

    if num_credentials_returned != 2:
        pytest.fail(
            f"Expected 2 credentials to be issued; got {num_credentials_returned}"
        )

    for cred in alice_cred_ex_response:
        cred_ex_id = cred["credential_exchange_id"]
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}/request", json={}
        )

        # wait for credential state "done" for each credential
        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": cred_ex_id,
            },
        )

    faber_records = (await faber_anoncreds_client.get(CREDENTIALS_BASE_PATH)).json()

    faber_cred_ex_response = (
        await faber_anoncreds_client.get(CREDENTIALS_BASE_PATH + "?state=done")
    ).json()
    filtered_cred_ex_records = [
        record
        for record in faber_cred_ex_response
        if record["credential_exchange_id"] in faber_cred_ids
    ]
    assert len(filtered_cred_ex_records) == 2

    faber_cred_ex_response = (
        await faber_anoncreds_client.get(CREDENTIALS_BASE_PATH + "?role=issuer")
    ).json()
    filtered_cred_ex_records = [
        record
        for record in faber_cred_ex_response
        if record["credential_exchange_id"] in faber_cred_ids
    ]
    assert len(filtered_cred_ex_records) == 2

    faber_cred_ex_response = (
        await faber_anoncreds_client.get(
            f"{CREDENTIALS_BASE_PATH}?thread_id={faber_records[0]['thread_id']}"
        )
    ).json()
    assert len(faber_cred_ex_response) == 1

    with pytest.raises(HTTPException) as exc:
        await faber_anoncreds_client.get(
            f"{CREDENTIALS_BASE_PATH}?connection_id=123&thread_id=123&role=asf&state=asd"
        )
    assert exc.value.status_code == 422
    assert len(json.loads(exc.value.detail)["detail"]) == 3
