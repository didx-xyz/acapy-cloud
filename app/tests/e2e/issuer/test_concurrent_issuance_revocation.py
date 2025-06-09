import asyncio

import pytest

from app.routes.issuer import router as issuer_router
from app.routes.revocation import router as revocation_router
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.regression_testing import TestMode
from app.tests.util.webhooks import check_webhook_state
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = issuer_router.prefix
REVOCATION_BASE_PATH = revocation_router.prefix


async def check_unique_cred_rev_ids(
    client: RichAsyncClient, credential_exchange_ids: list[str]
) -> None:
    """Check that all credential revocation IDs are unique."""
    seen = []

    for cred_ex_id in credential_exchange_ids:
        response = await client.get(
            f"{REVOCATION_BASE_PATH}/revocation/record?credential_exchange_id={cred_ex_id}"
        )
        response.raise_for_status()
        revocation_record = response.json()

        cred_rev_id = int(revocation_record["cred_rev_id"])
        if cred_rev_id not in seen:
            seen.append(cred_rev_id)
        else:
            raise AssertionError(
                f"Duplicate cred_rev_id found: {cred_rev_id} for credential {cred_ex_id}"
            )

    print(f"Unique cred_rev_ids found: {len(seen)}")
    seen.sort()
    print(f"Credential revocation IDs: {seen}")


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Do not test multi-issuance and revocation in regression mode",
)
async def test_concurrent_issuance_sequential_revocation(
    faber_anoncreds_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id_revocable: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
):
    # Fetch existing records so we can filter to exclude them
    existing_records = (
        await alice_member_client.get(CREDENTIALS_BASE_PATH + "?state=offer-received")
    ).json()

    faber_conn_id = faber_anoncreds_and_alice_connection.faber_connection_id
    num_creds = 10  # Number of credentials to issue concurrently

    # Create and send credential offers concurrently
    faber_cred_ex_ids = []
    for i in range(num_creds):
        credential = {
            "connection_id": faber_conn_id,
            "save_exchange_record": True,
            "anoncreds_credential_detail": {
                "credential_definition_id": anoncreds_credential_definition_id_revocable,
                "attributes": {"speed": str(i), "name": "Alice", "age": "44"},
            },
        }

        response = await faber_anoncreds_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
        faber_cred_ex_ids.append(response.json()["credential_exchange_id"])

    # Wait for all credentials to be received by Alice
    num_tries = 0
    num_credentials_returned = 0
    while (
        num_credentials_returned != num_creds and num_tries < 20
    ):  # Increased timeout for many creds
        await asyncio.sleep(0.5)
        alice_cred_ex_response = (
            await alice_member_client.get(
                f"{CREDENTIALS_BASE_PATH}?connection_id={faber_anoncreds_and_alice_connection.alice_connection_id}"
            )
        ).json()
        alice_cred_ex_response = [
            record
            for record in alice_cred_ex_response
            if record not in existing_records
        ]
        num_credentials_returned = len(alice_cred_ex_response)
        num_tries += 1

    assert num_credentials_returned == num_creds, (
        f"Expected {num_creds} credentials to be issued; only got {num_credentials_returned}"
    )

    # Accept all credentials concurrently using asyncio.gather()
    request_tasks = []
    for cred in alice_cred_ex_response:
        task = alice_member_client.post(
            f"{CREDENTIALS_BASE_PATH}/{cred['credential_exchange_id']}/request", json={}
        )
        request_tasks.append(task)

    # Execute all credential requests concurrently
    await asyncio.gather(*request_tasks)

    # Wait for all credentials to be in 'done' state concurrently
    webhook_tasks = [
        check_webhook_state(
            client=alice_member_client,
            topic="credentials",
            state="done",
            filter_map={
                "credential_exchange_id": cred["credential_exchange_id"],
            },
        )
        for cred in alice_cred_ex_response
    ]
    await asyncio.gather(*webhook_tasks)

    # Get all credential exchange records
    cred_ex_response = (
        await faber_anoncreds_client.get(
            CREDENTIALS_BASE_PATH + "?connection_id=" + faber_conn_id
        )
    ).json()
    cred_ex_response = [
        record
        for record in cred_ex_response
        if record["credential_exchange_id"] in faber_cred_ex_ids
    ]

    assert len(cred_ex_response) == num_creds
    credentials = [CredentialExchange(**cred) for cred in cred_ex_response]

    # Check that all credential revocation IDs are unique before revocation
    await check_unique_cred_rev_ids(faber_anoncreds_client, faber_cred_ex_ids)

    # Sequentially revoke each credential
    for cred in credentials:
        response = await faber_anoncreds_client.post(
            f"{REVOCATION_BASE_PATH}/revoke",
            json={
                "credential_exchange_id": cred.credential_exchange_id,
                "auto_publish_on_ledger": True,
            },
        )
        assert response.status_code == 200
        assert len(response.json()["cred_rev_ids_published"]) == 1

        # Verify the credential is revoked
        rev_record = (
            await faber_anoncreds_client.get(
                f"{REVOCATION_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_exchange_id
            )
        ).json()
        assert rev_record["state"] == "revoked"
