import asyncio
from typing import Literal

import pytest
from fastapi import HTTPException

from app.routes.revocation import router
from app.routes.verifier import router as verifier_router
from app.tests.util.regression_testing import TestMode
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

# Apply the marker to all tests in this module
pytestmark = pytest.mark.xdist_group(name="issuer_test_group")

REVOCATION_BASE_PATH = router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix

skip_regression_test_reason = "Skip publish-revocations in regression mode"


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_clear_pending_revokes_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    revoke_alice_anoncreds: list[CredentialExchange],
):
    with pytest.raises(HTTPException) as exc:
        await clear_pending_revokes(faber_anoncreds_client, revoke_alice_anoncreds)
    assert exc.value.status_code == 501
    assert (
        "Clearing pending revocations is not yet supported for AnonCreds."
        in exc.value.detail
    )


async def clear_pending_revokes(
    faber_client: RichAsyncClient,
    revoke_alice_creds: list[CredentialExchange],
):
    faber_cred_ex_id = revoke_alice_creds[0].credential_exchange_id
    revocation_record_response = await faber_client.get(
        f"{REVOCATION_BASE_PATH}/revocation/record"
        + "?credential_exchange_id="
        + faber_cred_ex_id
    )

    rev_reg_id = revocation_record_response.json()["rev_reg_id"]
    cred_rev_id = revocation_record_response.json()["cred_rev_id"]

    clear_revoke_response = await faber_client.post(
        f"{REVOCATION_BASE_PATH}/clear-pending-revocations",
        json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
    )
    revocation_registry_credential_map = clear_revoke_response.json()[
        "revocation_registry_credential_map"
    ]

    for key in revocation_registry_credential_map:
        assert len(revocation_registry_credential_map[key]) >= 2, (
            "We expect at least two cred_rev_ids per rev_reg_id after revoking one"
        )

    # clear_revoke_response = await faber_client.post(
    #     f"{REVOCATION_BASE_PATH}/clear-pending-revocations",
    #     json={"revocation_registry_credential_map": {rev_reg_id: []}},
    # )
    # revocation_registry_credential_map = clear_revoke_response.json()[
    #     "revocation_registry_credential_map"
    # ]
    # todo: aca-py now provides response. Make assertions based on response

    for cred in revoke_alice_creds:
        rev_record = (
            await faber_client.get(
                f"{REVOCATION_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_exchange_id
            )
        ).json()

        assert rev_record["state"] == "issued"

    # Test for cred_rev_id not pending
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
        )
    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_clear_pending_revokes_bad_payload_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
):
    with pytest.raises(HTTPException) as exc:
        await faber_anoncreds_client.post(
            f"{REVOCATION_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": "bad"},
        )

    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        await faber_anoncreds_client.post(
            f"{REVOCATION_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {"bad": "bad"}},
        )

    assert exc.value.status_code == 422


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_publish_all_revocations_for_rev_reg_id_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    revoke_alice_anoncreds: list[CredentialExchange],
):
    await publish_all_revocations_for_rev_reg_id(
        "anoncreds", faber_anoncreds_client, revoke_alice_anoncreds
    )


async def publish_all_revocations_for_rev_reg_id(
    credential_type: Literal["anoncreds"],
    faber_client: RichAsyncClient,
    revoke_alice_creds: list[CredentialExchange],
):
    faber_cred_ex_id = revoke_alice_creds[0].credential_exchange_id
    response = (
        await faber_client.get(
            f"{REVOCATION_BASE_PATH}/revocation/record"
            + "?credential_exchange_id="
            + faber_cred_ex_id
        )
    ).json()

    rev_reg_id = response["rev_reg_id"]

    await faber_client.post(
        f"{REVOCATION_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {rev_reg_id: []}},
    )

    if credential_type == "anoncreds":
        # TODO: Remove this once anoncreds returns transaction id to be awaited
        await asyncio.sleep(10)

    await check_revocation_status(faber_client, revoke_alice_creds, "revoked")


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_publish_all_revocations_no_payload_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    revoke_alice_anoncreds: list[CredentialExchange],
):
    await publish_all_revocations_no_payload(
        faber_anoncreds_client, revoke_alice_anoncreds
    )


async def publish_all_revocations_no_payload(
    faber_client: RichAsyncClient,
    revoke_alice_creds: list[CredentialExchange],
):
    await faber_client.post(
        f"{REVOCATION_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {}},
    )

    await check_revocation_status(faber_client, revoke_alice_creds, "revoked")


async def check_revocation_status(
    client: RichAsyncClient,
    credentials: list[CredentialExchange],
    expected_state: str,
):
    for cred in credentials:
        rev_record = (
            await client.get(
                f"{REVOCATION_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_exchange_id
            )
        ).json()

        assert rev_record["state"] == expected_state


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_publish_one_revocation_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    revoke_alice_anoncreds: list[CredentialExchange],
):
    await publish_one_revocation(faber_anoncreds_client, revoke_alice_anoncreds)


async def publish_one_revocation(
    faber_client: RichAsyncClient,
    revoke_alice_creds: list[CredentialExchange],
):
    faber_cred_ex_id = revoke_alice_creds[0].credential_exchange_id
    response = (
        await faber_client.get(
            f"{REVOCATION_BASE_PATH}/revocation/record"
            + "?credential_exchange_id="
            + faber_cred_ex_id
        )
    ).json()

    rev_reg_id = response["rev_reg_id"]
    cred_rev_id = response["cred_rev_id"]
    await faber_client.post(
        f"{REVOCATION_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
    )

    for cred in revoke_alice_creds:
        rev_record = (
            await faber_client.get(
                f"{REVOCATION_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_exchange_id
            )
        ).json()

        if rev_record["cred_rev_id"] == cred_rev_id:
            assert rev_record["state"] == "revoked"
        else:
            assert rev_record["state"] == "issued"

    # Test for cred_rev_id not pending
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_publish_revocations_bad_payload_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
):
    await publish_revocations_bad_payload(faber_anoncreds_client)


async def publish_revocations_bad_payload(
    faber_client: RichAsyncClient,
):
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": "bad"},
        )

    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": {"bad": "bad"}},
        )

    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{REVOCATION_BASE_PATH}/publish-revocations",
            json={
                "revocation_registry_credential_map": {
                    "WgWxqztrNooG92RXvxSTWv:4:WgWxqztrNooG92RXvxSTWv:3:CL:20:tag:CL_ACCUM:0": []
                }
            },
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_pending_revocations_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
    revoke_alice_anoncreds: list[CredentialExchange],
):
    faber_cred_ex_id = revoke_alice_anoncreds[0].credential_exchange_id
    revocation_record_response = await faber_anoncreds_client.get(
        f"{REVOCATION_BASE_PATH}/revocation/record"
        f"?credential_exchange_id={faber_cred_ex_id}"
    )

    rev_reg_id = revocation_record_response.json()["rev_reg_id"]

    pending_revocations = (
        await faber_anoncreds_client.get(
            f"{REVOCATION_BASE_PATH}/get-pending-revocations/{rev_reg_id}"
        )
    ).json()["pending_cred_rev_ids"]

    assert (
        len(pending_revocations) >= 3
    )  # we expect at least 3 cred_rev_ids can be more if whole module is run


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_pending_revocations_bad_payload_anoncreds(
    faber_anoncreds_client: RichAsyncClient,
):
    with pytest.raises(HTTPException) as exc:
        await faber_anoncreds_client.get(
            f"{REVOCATION_BASE_PATH}/get-pending-revocations/bad"
        )

    # TODO: AnonCreds endpoint doesn't validate rev_reg_id
    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip("TODO: AnonCreds endpoint doesn't validate rev_reg_id")
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_fix_rev_reg_bad_id_anoncreds(
    faber_anoncreds_client: RichAsyncClient, rev_reg_id: str, status_code: int
):
    await fix_rev_reg_bad_id(faber_anoncreds_client, rev_reg_id, status_code)


async def fix_rev_reg_bad_id(
    faber_client: RichAsyncClient, rev_reg_id: str, status_code: int
):
    with pytest.raises(HTTPException) as exc:
        await faber_client.put(
            f"{REVOCATION_BASE_PATH}/fix-revocation-registry/{rev_reg_id}",
            params={"apply_ledger_update": False},
        )

    assert exc.value.status_code == status_code
