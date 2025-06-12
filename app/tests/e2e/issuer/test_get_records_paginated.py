import asyncio

import pytest
from fastapi import HTTPException

from app.routes.issuer import router
from app.tests.util.connections import FaberAliceConnect
from app.tests.util.regression_testing import TestMode
from shared import RichAsyncClient

CREDENTIALS_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Temporarily skip; existing tests on dev don't clean up old records yet",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_credential_exchange_records_paginated(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    faber_anoncreds_and_alice_connection: FaberAliceConnect,
) -> None:
    issuer_client = faber_anoncreds_client
    connection = faber_anoncreds_and_alice_connection
    credential_definition_id = anoncreds_credential_definition_id

    issuer_connection_id = connection.faber_connection_id

    num_credentials_to_test = 5
    test_attributes = {"name": "Alice", "age": "44"}

    faber_cred_ex_ids = []
    alice_cred_ex_records = []
    try:
        # Create multiple credential exchanges
        for i in range(num_credentials_to_test):
            test_attributes["speed"] = str(i)
            credential_v2 = {
                "connection_id": issuer_connection_id,
                "anoncreds_credential_detail": {
                    "credential_definition_id": credential_definition_id,
                    "attributes": test_attributes,
                },
                "save_exchange_record": True,
            }

            response = await issuer_client.post(
                CREDENTIALS_BASE_PATH, json=credential_v2
            )

            credential_exchange_id = response.json()["credential_exchange_id"]
            faber_cred_ex_ids.append(credential_exchange_id)

        # Test different limits
        for limit in range(1, num_credentials_to_test + 2):
            num_tries = 0
            retry = True
            while retry and num_tries < 5:  # Handle case where record doesn't exist yet
                response = await alice_member_client.get(
                    CREDENTIALS_BASE_PATH,
                    params={
                        "state": "offer-received",
                        "limit": limit,
                    },
                )
                credentials = response.json()
                expected_num = min(limit, num_credentials_to_test)
                if len(credentials) != expected_num:
                    num_tries += 1
                    await asyncio.sleep(0.2)
                else:
                    retry = False
            assert not retry, (
                f"Expected {expected_num} records, got {len(credentials)}: {credentials}"
            )

        # Test ascending order
        response = await alice_member_client.get(
            CREDENTIALS_BASE_PATH,
            params={
                "state": "offer-received",
                "limit": num_credentials_to_test,
                "descending": False,
            },
        )
        credentials_asc = response.json()
        assert len(credentials_asc) == num_credentials_to_test

        # Verify that the credentials are in ascending order based on created_at
        assert credentials_asc == sorted(
            credentials_asc, key=lambda x: x["created_at"], reverse=False
        )

        # Test descending order
        response = await alice_member_client.get(
            CREDENTIALS_BASE_PATH,
            params={
                "state": "offer-received",
                "limit": num_credentials_to_test,
                "descending": True,
            },
        )
        credentials_desc = response.json()
        assert len(credentials_desc) == num_credentials_to_test

        # Verify that the credentials are in descending order based on created_at
        assert credentials_desc == sorted(
            credentials_desc, key=lambda x: x["created_at"], reverse=True
        )

        # Compare ascending and descending order results
        assert credentials_desc == sorted(
            credentials_asc, key=lambda x: x["created_at"], reverse=True
        )

        # Test offset greater than number of records
        response = await alice_member_client.get(
            CREDENTIALS_BASE_PATH,
            params={
                "state": "offer-received",
                "limit": 1,
                "offset": num_credentials_to_test,
            },
        )
        credentials = response.json()
        assert len(credentials) == 0

        # Test fetching unique records with pagination
        for offset in range(num_credentials_to_test):
            response = await alice_member_client.get(
                CREDENTIALS_BASE_PATH,
                params={
                    "state": "offer-received",
                    "limit": 1,
                    "offset": offset,
                },
            )

            credentials = response.json()
            assert len(credentials) == 1

            record = credentials[0]
            assert record not in alice_cred_ex_records
            alice_cred_ex_records.append(record)

        # Test invalid limit and offset values
        invalid_params = [
            {"limit": -1},  # must be positive
            {"offset": -1},  # must be positive
            {"limit": 0},  # must be greater than 0
            {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
        ]

        for params in invalid_params:
            with pytest.raises(HTTPException) as exc:
                await issuer_client.get(CREDENTIALS_BASE_PATH, params=params)
            assert exc.value.status_code == 422

    finally:
        # Clean up created credential exchange records
        for cred_ex_id in faber_cred_ex_ids:
            await issuer_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")
        for alice_record in alice_cred_ex_records:
            cred_ex_id = alice_record["credential_exchange_id"]
            await alice_member_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")
