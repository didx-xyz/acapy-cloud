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
async def test_get_credential_exchange_records_paginated(
    faber_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    credential_definition_id: str,
    faber_and_alice_connection: FaberAliceConnect,
):
    num_credentials_to_test = 5
    test_attributes = {"name": "Alice", "age": "44"}

    faber_cred_ex_ids = []
    alice_prev_credentials = []
    try:
        # Create multiple credential exchanges
        for i in range(num_credentials_to_test):
            test_attributes["speed"] = str(i)
            credential_v2 = {
                "protocol_version": "v2",
                "connection_id": faber_and_alice_connection.faber_connection_id,
                "indy_credential_detail": {
                    "credential_definition_id": credential_definition_id,
                    "attributes": test_attributes,
                },
                "save_exchange_record": True,
            }

            response = await faber_client.post(
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
                        "state": "offer-sent",
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
            assert (
                not retry
            ), f"Expected {expected_num} records, got {len(credentials)}: {credentials}"

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
            assert record not in alice_prev_credentials
            alice_prev_credentials.append(record)

        # Test invalid limit and offset values
        invalid_params = [
            {"limit": -1},  # must be positive
            {"offset": -1},  # must be positive
            {"limit": 0},  # must be greater than 0
            {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
        ]

        for params in invalid_params:
            with pytest.raises(HTTPException) as exc:
                await faber_client.get(CREDENTIALS_BASE_PATH, params=params)
            assert exc.value.status_code == 422

    finally:
        # Clean up created credentials
        for cred_ex_id in faber_cred_ex_ids:
            await faber_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")
        for alice_credential in alice_prev_credentials:
            cred_ex_id = alice_credential["credential_exchange_id"]
            await alice_member_client.delete(f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}")
