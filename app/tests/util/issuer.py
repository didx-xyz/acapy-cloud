import asyncio

import pytest

from app.tests.fixtures.credentials import CREDENTIALS_BASE_PATH
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.webhooks import check_webhook_state
from shared.models.credential_exchange import CredentialExchange
from shared.util.rich_async_client import RichAsyncClient


async def _issue_credential_core(
    issuer_client: RichAsyncClient,
    holder_client: RichAsyncClient,
    credential_definition_id: str,
    issuer_connection_id: str,
    holder_connection_id: str,
    attributes: dict,
    holder_index: int,
) -> CredentialExchange:
    """Core logic for issuing a single credential."""
    # Issue credential
    credential = {
        "connection_id": issuer_connection_id,
        "save_exchange_record": True,
        "anoncreds_credential_detail": {
            "credential_definition_id": credential_definition_id,
            "attributes": attributes,
        },
    }

    issuer_cred_ex_id = (
        await issuer_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
    ).json()["credential_exchange_id"]

    # Wait for holder to receive the credential offer
    num_tries = 0
    holder_cred_ex = None
    while holder_cred_ex is None and num_tries < 10:
        await asyncio.sleep(0.25)
        holder_cred_ex_response = (
            await holder_client.get(
                f"{CREDENTIALS_BASE_PATH}?connection_id={holder_connection_id}"
            )
        ).json()
        if holder_cred_ex_response:
            holder_cred_ex = holder_cred_ex_response[0]
        num_tries += 1

    if holder_cred_ex is None:
        pytest.fail(f"Holder {holder_index} did not receive credential offer")

    cred_ex_id = holder_cred_ex["credential_exchange_id"]

    # Holder requests the credential
    await holder_client.post(
        f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}/request?save_exchange_record=true",
        json={},
    )

    # Wait for credential state "done"
    await check_webhook_state(
        client=holder_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_exchange_id": cred_ex_id,
        },
    )

    # Get the final credential exchange record from issuer
    issuer_cred_ex_response = (
        await issuer_client.get(f"{CREDENTIALS_BASE_PATH}/{issuer_cred_ex_id}")
    ).json()

    return CredentialExchange(**issuer_cred_ex_response)


async def _revoke_credential_core(
    issuer_client: RichAsyncClient,
    credential_exchange_id: str,
    auto_publish: bool = True,
) -> None:
    """Core logic for revoking a single credential."""
    await issuer_client.post(
        f"{CREDENTIALS_BASE_PATH}/revoke",
        json={
            "credential_exchange_id": credential_exchange_id,
            "auto_publish_on_ledger": auto_publish,
        },
    )


async def issue_single_credential(
    issuer_client: RichAsyncClient,
    holder_client: RichAsyncClient,
    credential_definition_id: str,
    connection: FaberAliceConnect,
    holder_index: int,
) -> CredentialExchange:
    """Issue a single credential to a holder and wait for completion."""
    attributes = {"speed": str(holder_index), "name": "Alice", "age": "44"}

    return await _issue_credential_core(
        issuer_client=issuer_client,
        holder_client=holder_client,
        credential_definition_id=credential_definition_id,
        issuer_connection_id=connection.faber_connection_id,
        holder_connection_id=connection.alice_connection_id,
        attributes=attributes,
        holder_index=holder_index,
    )


async def revoke_single_credential(
    issuer_client: RichAsyncClient,
    credential_exchange: CredentialExchange,
    auto_publish: bool = True,
) -> None:
    """Revoke a single credential."""
    await _revoke_credential_core(
        issuer_client=issuer_client,
        credential_exchange_id=credential_exchange.credential_exchange_id,
        auto_publish=auto_publish,
    )


async def revoke_many(
    faber_anoncreds_client: RichAsyncClient,
    issue_many_creds: list[CredentialExchange],
    auto_publish: bool = True,
) -> list[CredentialExchange]:
    """Revoke multiple credentials."""
    for cred in issue_many_creds:
        await _revoke_credential_core(
            issuer_client=faber_anoncreds_client,
            credential_exchange_id=cred.credential_exchange_id,
            auto_publish=auto_publish,
        )

    return issue_many_creds


async def issue_many_credentials(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
    num_to_issue: int = 15,
) -> list[CredentialExchange]:
    """Issue multiple credentials and wait for all to complete."""
    # Fetch existing records so we can filter to exclude them. Necessary to cater for long running / regression tests
    existing_records = (
        await alice_member_client.get(CREDENTIALS_BASE_PATH + "?state=offer-received")
    ).json()

    faber_conn_id = faber_anoncreds_and_alice_connection.faber_connection_id
    alice_conn_id = faber_anoncreds_and_alice_connection.alice_connection_id

    # Issue all credentials using the core function
    issued_credentials = []
    for i in range(num_to_issue):
        attributes = {"speed": str(i), "name": "Alice", "age": "44"}

        # Use core function but handle the batch processing differently
        credential = {
            "connection_id": faber_conn_id,
            "save_exchange_record": True,
            "anoncreds_credential_detail": {
                "credential_definition_id": anoncreds_credential_definition_id_revocable,
                "attributes": attributes,
            },
        }

        faber_cred_ex_id = (
            await faber_anoncreds_client.post(
                CREDENTIALS_BASE_PATH,
                json=credential,
            )
        ).json()["credential_exchange_id"]
        issued_credentials.append(faber_cred_ex_id)

    # Wait for all credentials to be received
    num_tries = 0
    num_credentials_returned = 0
    alice_cred_ex_response = []
    while num_credentials_returned != num_to_issue and num_tries < 10:
        await asyncio.sleep(0.25)
        alice_cred_ex_response = (
            await alice_member_client.get(
                f"{CREDENTIALS_BASE_PATH}?connection_id={alice_conn_id}"
            )
        ).json()
        alice_cred_ex_response = [
            record
            for record in alice_cred_ex_response
            if record not in existing_records
        ]
        num_credentials_returned = len(alice_cred_ex_response)
        num_tries += 1

    if num_credentials_returned != num_to_issue:
        pytest.fail(
            f"Expected {num_to_issue} credentials to be issued; only got {num_credentials_returned}"
        )

    # Process all credential requests
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

    # Get final credential exchange records from issuer
    cred_ex_response = (
        await faber_anoncreds_client.get(
            CREDENTIALS_BASE_PATH + "?connection_id=" + faber_conn_id
        )
    ).json()
    cred_ex_response = [
        record
        for record in cred_ex_response
        if record["credential_exchange_id"] in issued_credentials
    ]

    assert len(cred_ex_response) == num_to_issue

    return [CredentialExchange(**cred) for cred in cred_ex_response]
