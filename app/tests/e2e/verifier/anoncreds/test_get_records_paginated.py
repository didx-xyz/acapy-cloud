import asyncio

import pytest
from fastapi import HTTPException

from app.routes.verifier import router
from app.tests.services.verifier.utils import sample_anoncreds_proof_request
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.regression_testing import TestMode
from app.tests.util.verifier import send_proof_request
from shared import RichAsyncClient

VERIFIER_BASE_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Temporarily skip; existing tests on dev don't clean up old records yet",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_presentation_exchange_records_paginated(
    acme_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    anoncreds_credential_definition_id: str,
    acme_and_alice_connection: AcmeAliceConnect,
):
    num_presentation_requests_to_test = 5

    acme_proof_ids = []
    alice_proof_records = []
    try:
        # Create multiple presentation requests
        for _ in range(num_presentation_requests_to_test):
            request_body = {
                "save_exchange_record": True,
                "connection_id": acme_and_alice_connection.acme_connection_id,
                "anoncreds_proof_request": sample_anoncreds_proof_request(
                    restrictions=[{"cred_def_id": anoncreds_credential_definition_id}]
                ).to_dict(),
            }
            response = await send_proof_request(acme_client, request_body)
            acme_proof_ids.append(response["proof_id"])

        # Test different limits
        for limit in range(1, num_presentation_requests_to_test + 2):
            num_tries = 0
            retry = True
            while retry and num_tries < 5:  # Handle case where record doesn't exist yet
                response = await alice_member_client.get(
                    f"{VERIFIER_BASE_PATH}/proofs",
                    params={
                        "state": "request-received",
                        "limit": limit,
                    },
                )
                proofs = response.json()
                expected_num = min(limit, num_presentation_requests_to_test)
                if len(proofs) != expected_num:
                    num_tries += 1
                    await asyncio.sleep(0.2)
                else:
                    retry = False
            assert not retry, (
                f"Expected {expected_num} records, got {len(proofs)}: {proofs}"
            )

        # Test ascending order
        response = await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs",
            params={
                "state": "request-received",
                "limit": num_presentation_requests_to_test,
                "descending": False,
            },
        )
        proofs_asc = response.json()
        assert len(proofs_asc) == num_presentation_requests_to_test

        # Verify that the proofs are in ascending order based on created_at
        assert proofs_asc == sorted(
            proofs_asc, key=lambda x: x["created_at"], reverse=False
        )

        # Test descending order
        response = await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs",
            params={
                "state": "request-received",
                "limit": num_presentation_requests_to_test,
                "descending": True,
            },
        )
        proofs_desc = response.json()
        assert len(proofs_desc) == num_presentation_requests_to_test

        # Verify that the proofs are in descending order based on created_at
        assert proofs_desc == sorted(
            proofs_desc, key=lambda x: x["created_at"], reverse=True
        )

        # Compare ascending and descending order results
        assert proofs_desc == sorted(
            proofs_asc, key=lambda x: x["created_at"], reverse=True
        )

        # Test offset greater than number of records
        response = await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs",
            params={
                "state": "request-received",
                "limit": 1,
                "offset": num_presentation_requests_to_test,
            },
        )
        proofs = response.json()
        assert len(proofs) == 0

        # Test fetching unique records with pagination
        for offset in range(num_presentation_requests_to_test):
            response = await alice_member_client.get(
                f"{VERIFIER_BASE_PATH}/proofs",
                params={
                    "state": "request-received",
                    "limit": 1,
                    "offset": offset,
                },
            )

            proofs = response.json()
            assert len(proofs) == 1

            record = proofs[0]
            assert record not in alice_proof_records
            alice_proof_records.append(record)

        # Test invalid limit and offset values
        invalid_params = [
            {"limit": -1},  # must be positive
            {"offset": -1},  # must be positive
            {"limit": 0},  # must be greater than 0
            {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
        ]

        for params in invalid_params:
            with pytest.raises(HTTPException) as exc:
                await acme_client.get(f"{VERIFIER_BASE_PATH}/proofs", params=params)
            assert exc.value.status_code == 422

    finally:
        # Clean up created presentation requests
        for proof_id in acme_proof_ids:
            await acme_client.delete(f"{VERIFIER_BASE_PATH}/proofs/{proof_id}")
        for alice_proof_record in alice_proof_records:
            proof_id = alice_proof_record["proof_id"]
            await alice_member_client.delete(f"{VERIFIER_BASE_PATH}/proofs/{proof_id}")
