import asyncio
from typing import List
from urllib.parse import quote

import pytest
from pydantic import BaseModel

from app.routes.issuer import router
from app.routes.wallet.credentials import router as wallets_router
from app.tests.util.connections import FaberAliceConnect, MeldCoAliceConnect
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = router.prefix
WALLET = wallets_router.prefix

sample_credential_attributes = {"speed": "10", "name": "Alice", "age": "44"}


class ReferentCredDef(BaseModel):
    referent: str
    cred_def_revocable: str


@pytest.fixture(scope="function")
async def issue_credential_to_alice(
    faber_client: RichAsyncClient,
    credential_definition_id: str,
    faber_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    credential = {
        "protocol_version": "v1",
        "connection_id": faber_and_alice_connection.faber_connection_id,
        "indy_credential_detail": {
            "credential_definition_id": credential_definition_id,
            "attributes": sample_credential_attributes,
        },
    }

    # create and send credential offer
    faber_send_response = await faber_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    thread_id = faber_send_response.json()["thread_id"]

    payload = await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="offer-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    alice_credential_id = payload["credential_id"]

    # send credential request - holder
    response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_credential_id}/request", json={}
    )

    await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_id": alice_credential_id,
        },
    )

    return response.json()


@pytest.fixture(scope="function")
async def meld_co_issue_credential_to_alice(
    meld_co_client: RichAsyncClient,
    meld_co_credential_definition_id: str,
    meld_co_and_alice_connection: MeldCoAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    credential = {
        "protocol_version": "v1",
        "connection_id": meld_co_and_alice_connection.meld_co_connection_id,
        "indy_credential_detail": {
            "credential_definition_id": meld_co_credential_definition_id,
            "attributes": sample_credential_attributes,
        },
    }

    # create and send credential offer- issuer
    meld_co_send_response = await meld_co_client.post(
        CREDENTIALS_BASE_PATH,
        json=credential,
    )
    thread_id = meld_co_send_response.json()["thread_id"]

    payload = await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="offer-received",
        filter_map={
            "thread_id": thread_id,
        },
    )

    alice_credential_id = payload["credential_id"]

    # send credential request - holder
    response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_credential_id}/request", json={}
    )

    await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_id": alice_credential_id,
        },
    )

    return response.json()


@pytest.fixture(scope="function")
async def issue_alice_creds_and_revoke_unpublished(
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id_revocable: str,
    faber_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:
    # Fetch existing records so we can filter to exclude them. Necessary to cater for long running / regression tests
    existing_records = (
        await alice_member_client.get(CREDENTIALS_BASE_PATH + "?state=offer-received")
    ).json()

    faber_conn_id = faber_and_alice_connection.faber_connection_id

    faber_cred_ex_ids = []
    for i in range(3):
        credential = {
            "protocol_version": "v1",
            "connection_id": faber_conn_id,
            "save_exchange_record": True,
            "indy_credential_detail": {
                "credential_definition_id": credential_definition_id_revocable,
                "attributes": {"speed": str(i), "name": "Alice", "age": "44"},
            },
        }

        faber_send_response = await faber_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
        cred_ex_id = faber_send_response.json()["credential_id"]
        faber_cred_ex_ids += [cred_ex_id]

    num_tries = 0
    num_credentials_returned = 0
    while num_credentials_returned != 3 and num_tries < 10:
        await asyncio.sleep(0.25)
        alice_cred_ex_response = (
            await alice_member_client.get(
                f"{CREDENTIALS_BASE_PATH}?connection_id={faber_and_alice_connection.alice_connection_id}"
            )
        ).json()
        alice_cred_ex_response = [
            record
            for record in alice_cred_ex_response
            if record not in existing_records
        ]
        num_credentials_returned = len(alice_cred_ex_response)
        num_tries += 1

    if num_credentials_returned != 3:
        raise Exception(
            f"Expected 3 credentials to be issued; only got {num_credentials_returned}"
        )

    for cred in alice_cred_ex_response:
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{cred['credential_id']}/request", json={}
        )
        # wait for credential state "done" for each credential
        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_id": cred["credential_id"],
            },
        )

    cred_ex_response = (
        await faber_client.get(
            CREDENTIALS_BASE_PATH + "?connection_id=" + faber_conn_id
        )
    ).json()
    cred_ex_response = [
        record
        for record in cred_ex_response
        if record["credential_id"] in faber_cred_ex_ids
    ]

    assert len(cred_ex_response) == 3

    # revoke all credentials in list
    for cred in cred_ex_response:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": cred["credential_id"][3:],
            },
        )

    credential_exchange_records = [
        CredentialExchange(**cred) for cred in cred_ex_response
    ]
    return credential_exchange_records


@pytest.fixture(scope="function")
async def issue_alice_creds_and_revoke_published(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[  # pylint: disable=redefined-outer-name
        CredentialExchange
    ],
) -> List[CredentialExchange]:
    credential_exchange_records = issue_alice_creds_and_revoke_unpublished
    # Publish revoked credentials
    await faber_client.post(
        f"{CREDENTIALS_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {}},
    )

    return credential_exchange_records


@pytest.fixture(scope="function")
async def get_or_issue_regression_cred_revoked(
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id_revocable: str,
    faber_and_alice_connection: FaberAliceConnect,
) -> ReferentCredDef:

    wql = quote('{"attr::name::value":"Alice-revoked"}')

    results = (await alice_member_client.get(f"{WALLET}?wql={wql}")).json()["results"]

    if len(results) == 1 and results[0]["attributes"]["name"] == "Alice-revoked":
        return ReferentCredDef(
            referent=results[0]["referent"],
            cred_def_revocable=results[0]["cred_def_id"],
        )

    else:
        faber_connection_id = faber_and_alice_connection.faber_connection_id
        credential = {
            "protocol_version": "v2",
            "connection_id": faber_connection_id,
            "save_exchange_record": True,
            "indy_credential_detail": {
                "credential_definition_id": credential_definition_id_revocable,
                "attributes": {
                    "speed": "speed-revoked",
                    "name": "Alice-revoked",
                    "age": "44-revoked",
                },
            },
        }

        faber_send_response = await faber_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )

        faber_ex_id = faber_send_response.json()["credential_id"]

        cred_ex = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": faber_send_response.json()["thread_id"],
            },
        )

        alice_cred_ex_id = cred_ex["credential_id"]

        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_cred_ex_id}/request", json={}
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_id": alice_cred_ex_id,
            },
        )

        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": faber_ex_id,
                "credential_definition_id": credential_definition_id_revocable,
                "auto_publish_on_ledger": True,
            },
        )

        await asyncio.sleep(1)

        results = (await alice_member_client.get(f"{WALLET}?wql={wql}")).json()[
            "results"
        ]

        return ReferentCredDef(
            referent=results[0]["referent"],
            cred_def_revocable=results[0]["cred_def_id"],
        )
