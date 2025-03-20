import asyncio
from typing import List, Literal

import pytest
from pydantic import BaseModel

from app.routes.issuer import router
from app.routes.revocation import router as revocation_router
from app.routes.wallet.credentials import router as wallets_router
from app.tests.util.connections import FaberAliceConnect, MeldCoAliceConnect
from app.tests.util.regression_testing import assert_fail_on_recreating_fixtures
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = router.prefix
WALLET_BASE_PATH = wallets_router.prefix
REVOCATION_BASE_PATH = revocation_router.prefix
sample_credential_attributes = {"speed": "10", "name": "Alice", "age": "44"}


async def issue_credential_to_alice(
    credential_type: Literal["indy", "anoncreds"],
    faber_client: RichAsyncClient,
    indy_credential_definition_id: str,
    faber_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    credential = {
        "type": credential_type,
        "connection_id": faber_and_alice_connection.faber_connection_id,
        f"{credential_type}_credential_detail": {
            "credential_definition_id": indy_credential_definition_id,
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

    alice_credential_exchange_id = payload["credential_exchange_id"]

    # send credential request - holder
    response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}/request", json={}
    )

    await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_exchange_id": alice_credential_exchange_id,
        },
    )

    return response.json()


@pytest.fixture(scope="function")
async def issue_anoncreds_credential_to_alice(
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    return await issue_credential_to_alice(
        credential_type="anoncreds",
        faber_client=faber_anoncreds_client,
        indy_credential_definition_id=anoncreds_credential_definition_id,
        faber_and_alice_connection=faber_anoncreds_and_alice_connection,
        alice_member_client=alice_member_client,
    )


@pytest.fixture(scope="function")
async def issue_indy_credential_to_alice(
    faber_indy_client: RichAsyncClient,
    indy_credential_definition_id: str,
    faber_indy_and_alice_connection: FaberAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    return await issue_credential_to_alice(
        credential_type="indy",
        faber_client=faber_indy_client,
        indy_credential_definition_id=indy_credential_definition_id,
        faber_and_alice_connection=faber_indy_and_alice_connection,
        alice_member_client=alice_member_client,
    )


async def meld_co_issue_credential_to_alice(
    credential_type: Literal["indy", "anoncreds"],
    meld_co_client: RichAsyncClient,
    meld_co_credential_definition_id: str,
    meld_co_and_alice_connection: MeldCoAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    credential = {
        "type": credential_type,
        "connection_id": meld_co_and_alice_connection.meld_co_connection_id,
        f"{credential_type}_credential_detail": {
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

    alice_credential_exchange_id = payload["credential_exchange_id"]

    # send credential request - holder
    response = await alice_member_client.post(
        f"{CREDENTIALS_BASE_PATH}/{alice_credential_exchange_id}/request", json={}
    )

    await check_webhook_state(
        client=alice_member_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_exchange_id": alice_credential_exchange_id,
        },
    )

    return response.json()


@pytest.fixture(scope="function")
async def meld_co_issue_anoncreds_credential_to_alice(
    meld_co_anoncreds_client: RichAsyncClient,
    meld_co_anoncreds_credential_definition_id: str,
    meld_co_anoncreds_and_alice_connection: MeldCoAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    return await meld_co_issue_credential_to_alice(
        credential_type="anoncreds",
        meld_co_client=meld_co_anoncreds_client,
        meld_co_credential_definition_id=meld_co_anoncreds_credential_definition_id,
        meld_co_and_alice_connection=meld_co_anoncreds_and_alice_connection,
        alice_member_client=alice_member_client,
    )


@pytest.fixture(scope="function")
async def meld_co_issue_indy_credential_to_alice(
    meld_co_indy_client: RichAsyncClient,
    meld_co_indy_credential_definition_id: str,
    meld_co_indy_and_alice_connection: MeldCoAliceConnect,
    alice_member_client: RichAsyncClient,
) -> CredentialExchange:
    return await meld_co_issue_credential_to_alice(
        credential_type="indy",
        meld_co_client=meld_co_indy_client,
        meld_co_credential_definition_id=meld_co_indy_credential_definition_id,
        meld_co_and_alice_connection=meld_co_indy_and_alice_connection,
        alice_member_client=alice_member_client,
    )


async def issue_alice_creds(
    credential_type: Literal["indy", "anoncreds"],
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id: str,
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
            "type": credential_type,
            "connection_id": faber_conn_id,
            "save_exchange_record": True,
            f"{credential_type}_credential_detail": {
                "credential_definition_id": credential_definition_id,
                "attributes": {"speed": str(i), "name": "Alice", "age": "44"},
            },
        }

        faber_cred_ex_id = (
            await faber_client.post(
                CREDENTIALS_BASE_PATH,
                json=credential,
            )
        ).json()["credential_exchange_id"]
        faber_cred_ex_ids += [faber_cred_ex_id]

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
        pytest.fail(
            f"Expected 3 credentials to be issued; only got {num_credentials_returned}"
        )

    for cred in alice_cred_ex_response:
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{cred['credential_exchange_id']}/request", json={}
        )
        # wait for credential state "done" for each credential
        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": cred["credential_exchange_id"],
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
        if record["credential_exchange_id"] in faber_cred_ex_ids
    ]

    assert len(cred_ex_response) == 3

    return [CredentialExchange(**cred) for cred in cred_ex_response]


@pytest.fixture(scope="function")
async def issue_alice_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:
    return await issue_alice_creds(
        credential_type="anoncreds",
        faber_client=faber_anoncreds_client,
        alice_member_client=alice_member_client,
        credential_definition_id=anoncreds_credential_definition_id_revocable,
        faber_and_alice_connection=faber_anoncreds_and_alice_connection,
    )


@pytest.fixture(scope="function")
async def issue_alice_indy_creds(
    faber_indy_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    indy_credential_definition_id_revocable: str,
    faber_indy_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:
    return await issue_alice_creds(
        credential_type="indy",
        faber_client=faber_indy_client,
        alice_member_client=alice_member_client,
        credential_definition_id=indy_credential_definition_id_revocable,
        faber_and_alice_connection=faber_indy_and_alice_connection,
    )


async def revoke_alice_creds(
    faber_client: RichAsyncClient,
    alice_issued_creds: List[CredentialExchange],
) -> List[CredentialExchange]:

    for cred in alice_issued_creds:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": cred.credential_exchange_id,
            },
        )

    return alice_issued_creds


@pytest.fixture(scope="function")
async def revoke_alice_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    issue_alice_anoncreds,  # pylint: disable=redefined-outer-name
) -> List[CredentialExchange]:
    return await revoke_alice_creds(
        faber_client=faber_anoncreds_client,
        alice_issued_creds=issue_alice_anoncreds,
    )


@pytest.fixture(scope="function")
async def revoke_alice_indy_creds(
    faber_indy_client: RichAsyncClient,
    issue_alice_indy_creds,  # pylint: disable=redefined-outer-name
) -> List[CredentialExchange]:
    return await revoke_alice_creds(
        faber_client=faber_indy_client,
        alice_issued_creds=issue_alice_indy_creds,
    )


async def revoke_creds_and_publish(
    request,
    faber_client: RichAsyncClient,
    issued_creds: List[CredentialExchange],
) -> List[CredentialExchange]:

    auto_publish = False
    if hasattr(request, "param") and request.param == "auto_publish_true":
        auto_publish = True

    for cred in issued_creds:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": cred.credential_exchange_id,
                "auto_publish_on_ledger": auto_publish,
            },
        )
        await asyncio.sleep(2)

    if not auto_publish:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/publish-revocations",
            json={
                "revocation_registry_credential_map": {},
            },
        )

    return issued_creds


@pytest.fixture(scope="function")
async def revoke_alice_anoncreds_and_publish(
    request,
    faber_anoncreds_client: RichAsyncClient,
    issue_alice_anoncreds,  # pylint: disable=redefined-outer-name
) -> List[CredentialExchange]:
    return await revoke_creds_and_publish(
        request,
        faber_client=faber_anoncreds_client,
        issued_creds=issue_alice_anoncreds,
    )


@pytest.fixture(scope="function")
async def revoke_alice_indy_creds_and_publish(
    request,
    faber_indy_client: RichAsyncClient,
    issue_alice_indy_creds,  # pylint: disable=redefined-outer-name
) -> List[CredentialExchange]:
    return await revoke_creds_and_publish(
        request,
        faber_client=faber_indy_client,
        issued_creds=issue_alice_indy_creds,
    )


class ReferentCredDef(BaseModel):
    referent: str
    cred_def_revocable: str


async def get_or_issue_regression_cred_revoked(
    credential_type: Literal["indy", "anoncreds"],
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id: str,
    faber_and_alice_connection: FaberAliceConnect,
) -> ReferentCredDef:
    revoked_attribute_name = f"Alice-revoked-{credential_type}"

    # Wallet Query to fetch credential with this attribute name
    wql = f'{{"attr::name::value":"{revoked_attribute_name}"}}'
    params = {"wql": wql, "limit": 10000}

    response = await alice_member_client.get(WALLET_BASE_PATH, params=params)
    results = response.json()["results"]
    assert (
        len(results) < 2
    ), f"Should have 1 or 0 credentials with this attr name, got: {results}"

    if results:
        revoked_credential = results[0]
        assert (
            revoked_credential["attrs"]["name"] == revoked_attribute_name
        ), f"WQL returned unexpected credential: {revoked_credential}"

    else:
        all_creds = await alice_member_client.get(WALLET_BASE_PATH)
        assert_fail_on_recreating_fixtures(
            f"WQL response: {response.json()}\nAll creds: {all_creds.json()}"
        )
        # Cred doesn't yet exist; issue credential for regression testing
        credential = {
            "type": credential_type,
            "connection_id": faber_and_alice_connection.faber_connection_id,
            "save_exchange_record": True,
            f"{credential_type}_credential_detail": {
                "credential_definition_id": credential_definition_id,
                "attributes": {
                    "speed": "10",
                    "name": revoked_attribute_name,
                    "age": "44",
                },
            },
        }

        # Faber sends credential
        faber_send_response = await faber_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )

        faber_cred_ex_id = faber_send_response.json()["credential_exchange_id"]

        alice_payload = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": faber_send_response.json()["thread_id"],
            },
        )
        alice_cred_ex_id = alice_payload["credential_exchange_id"]

        # Alice accepts credential
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_cred_ex_id}/request", json={}
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": alice_cred_ex_id,
            },
        )

        # Faber revokes credential
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": faber_cred_ex_id,
                "auto_publish_on_ledger": True,
            },
        )

        # Alice fetches the revoked credential
        wallet_credentials = await alice_member_client.get(
            f"{WALLET_BASE_PATH}?wql={wql}"
        )
        revoked_credential = wallet_credentials.json()["results"][0]

    return ReferentCredDef(
        referent=revoked_credential["referent"],
        cred_def_revocable=revoked_credential["cred_def_id"],
    )


@pytest.fixture(scope="function")
async def get_or_issue_regression_anoncreds_revoked(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> ReferentCredDef:
    return await get_or_issue_regression_cred_revoked(
        credential_type="anoncreds",
        faber_client=faber_anoncreds_client,
        alice_member_client=alice_member_client,
        credential_definition_id=anoncreds_credential_definition_id_revocable,
        faber_and_alice_connection=faber_anoncreds_and_alice_connection,
    )


@pytest.fixture(scope="function")
async def get_or_issue_regression_indy_cred_revoked(
    faber_indy_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    indy_credential_definition_id_revocable: str,
    faber_indy_and_alice_connection: FaberAliceConnect,
) -> ReferentCredDef:
    return await get_or_issue_regression_cred_revoked(
        credential_type="indy",
        faber_client=faber_indy_client,
        alice_member_client=alice_member_client,
        credential_definition_id=indy_credential_definition_id_revocable,
        faber_and_alice_connection=faber_indy_and_alice_connection,
    )


async def get_or_issue_regression_cred_valid(
    credential_type: Literal["indy", "anoncreds"],
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id_revocable: str,
    faber_and_alice_connection: FaberAliceConnect,
):
    valid_credential_attribute_name = f"Alice-valid-{credential_type}"

    # Wallet Query to fetch credential with this attribute name
    wql = f'{{"attr::name::value":"{valid_credential_attribute_name}"}}'
    params = {"wql": wql, "limit": 10000}

    response = await alice_member_client.get(WALLET_BASE_PATH, params=params)

    results = response.json()["results"]
    assert (
        len(results) < 2
    ), f"Should have 1 or 0 credentials with this attr name, got: {results}"

    if results:
        valid_credential = results[0]
        assert (
            valid_credential["attrs"]["name"] == valid_credential_attribute_name
        ), f"WQL returned unexpected credential: {valid_credential}"

    else:
        all_creds = await alice_member_client.get(WALLET_BASE_PATH)
        assert_fail_on_recreating_fixtures(
            f"WQL response: {response.json()}\nAll creds: {all_creds.json()}"
        )
        # Cred doesn't yet exist; issue credential for regression testing
        credential = {
            "type": credential_type,
            "connection_id": faber_and_alice_connection.faber_connection_id,
            "save_exchange_record": True,
            f"{credential_type}_credential_detail": {
                "credential_definition_id": credential_definition_id_revocable,
                "attributes": {
                    "speed": "10",
                    "name": valid_credential_attribute_name,
                    "age": "44",
                },
            },
        }

        # Faber sends credential
        faber_send_response = await faber_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )

        alice_payload = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": faber_send_response.json()["thread_id"],
            },
        )
        alice_cred_ex_id = alice_payload["credential_exchange_id"]

        # Alice accepts credential
        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_cred_ex_id}/request", json={}
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": alice_cred_ex_id,
            },
        )

        # Alice fetches the valid credential
        wallet_credentials = await alice_member_client.get(
            f"{WALLET_BASE_PATH}?wql={wql}"
        )
        valid_credential = wallet_credentials.json()["results"][0]

    return ReferentCredDef(
        referent=valid_credential["referent"],
        cred_def_revocable=valid_credential["cred_def_id"],
    )


@pytest.fixture(scope="function")
async def get_or_issue_regression_anoncreds_valid(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
):
    return await get_or_issue_regression_cred_valid(
        credential_type="anoncreds",
        faber_client=faber_anoncreds_client,
        alice_member_client=alice_member_client,
        credential_definition_id_revocable=anoncreds_credential_definition_id_revocable,
        faber_and_alice_connection=faber_anoncreds_and_alice_connection,
    )


@pytest.fixture(scope="function")
async def get_or_issue_regression_indy_cred_valid(
    faber_indy_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    indy_credential_definition_id_revocable: str,
    faber_indy_and_alice_connection: FaberAliceConnect,
):
    return await get_or_issue_regression_cred_valid(
        credential_type="indy",
        faber_client=faber_indy_client,
        alice_member_client=alice_member_client,
        credential_definition_id_revocable=indy_credential_definition_id_revocable,
        faber_and_alice_connection=faber_indy_and_alice_connection,
    )


async def issue_alice_many_creds(
    credential_type: Literal["indy", "anoncreds"],
    request,
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id: str,
    faber_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:

    faber_conn_id = faber_and_alice_connection.faber_connection_id

    faber_cred_ex_ids = []
    num_creds = request.param if hasattr(request, "param") else 3
    for i in range(num_creds):
        credential = {
            "type": credential_type,
            "connection_id": faber_conn_id,
            "save_exchange_record": True,
            f"{credential_type}_credential_detail": {
                "credential_definition_id": credential_definition_id,
                "attributes": {"speed": str(i), "name": "Alice", "age": "44"},
            },
        }
        response = (
            await faber_client.post(
                CREDENTIALS_BASE_PATH,
                json=credential,
            )
        ).json()

        faber_cred_ex_id = response["credential_exchange_id"]
        faber_cred_ex_ids += [faber_cred_ex_id]

        thread_id = response["thread_id"]

        alice_event = await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="offer-received",
            filter_map={
                "thread_id": thread_id,
            },
        )
        alice_cred_ex_id = alice_event["credential_exchange_id"]

        await alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{alice_cred_ex_id}/request",
            json={},
        )

        await check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "thread_id": thread_id,
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
        if record["credential_exchange_id"] in faber_cred_ex_ids
    ]

    assert len(cred_ex_response) == num_creds

    return [CredentialExchange(**cred) for cred in cred_ex_response]


@pytest.fixture(scope="function")
async def issue_alice_many_anoncreds(
    request,
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:
    return await issue_alice_many_creds(
        credential_type="anoncreds",
        request=request,
        faber_client=faber_anoncreds_client,
        alice_member_client=alice_member_client,
        credential_definition_id=anoncreds_credential_definition_id,
        faber_and_alice_connection=faber_anoncreds_and_alice_connection,
    )


@pytest.fixture(scope="function")
async def issue_alice_many_indy_creds(
    request,
    faber_indy_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    indy_credential_definition_id: str,
    faber_indy_and_alice_connection: FaberAliceConnect,
) -> List[CredentialExchange]:
    return await issue_alice_many_creds(
        credential_type="indy",
        request=request,
        faber_client=faber_indy_client,
        alice_member_client=alice_member_client,
        credential_definition_id=indy_credential_definition_id,
        faber_and_alice_connection=faber_indy_and_alice_connection,
    )
