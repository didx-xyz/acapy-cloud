from typing import List

import pytest
from assertpy import assert_that
from fastapi import HTTPException

from app.routes.issuer import router
from app.routes.verifier import router as verifier_router
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

CREDENTIALS_BASE_PATH = router.prefix
VERIFIER_BASE_PATH = verifier_router.prefix


@pytest.mark.anyio
async def test_clear_pending_revokes(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[CredentialExchange],
):
    faber_cred_ex_id = issue_alice_creds_and_revoke_unpublished[0].credential_id[3:]
    response = (
        await faber_client.get(
            f"{CREDENTIALS_BASE_PATH}/revocation/record"
            + "?credential_exchange_id="
            + faber_cred_ex_id
        )
    ).json()

    rev_reg_id = response["rev_reg_id"]
    clear_revoke_response = (
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: ["1"]}},
        )
    ).json()["revocation_registry_credential_map"]

    for key in clear_revoke_response:
        assert len(clear_revoke_response[key]) == 2

    clear_revoke_response = (
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: []}},
        )
    ).json()["revocation_registry_credential_map"]

    assert clear_revoke_response == {}

    for cred in issue_alice_creds_and_revoke_unpublished:
        rev_record = (
            await faber_client.get(
                f"{CREDENTIALS_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_id[3:]
            )
        ).json()

        assert rev_record["state"] == "issued"

    # Test for cred_rev_id not pending
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: ["1"]}},
        )
    assert_that(exc.value.status_code).is_equal_to(404)


@pytest.mark.anyio
async def test_clear_pending_revokes_no_map(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[CredentialExchange],
):
    clear_revoke_response = (
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {}},
        )
    ).json()["revocation_registry_credential_map"]

    assert clear_revoke_response == {}

    for cred in issue_alice_creds_and_revoke_unpublished:
        rev_record = (
            await faber_client.get(
                f"{CREDENTIALS_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_id[3:]
            )
        ).json()

        assert rev_record["state"] == "issued"


@pytest.mark.anyio
async def test_clear_pending_revokes_bad_payload(
    faber_client: RichAsyncClient,
):
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": "bad"},
        )

    assert_that(exc.value.status_code).is_equal_to(422)

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={"revocation_registry_credential_map": {"bad": "bad"}},
        )

    assert_that(exc.value.status_code).is_equal_to(422)

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/clear-pending-revocations",
            json={
                "revocation_registry_credential_map": {
                    "WgWxqztrNooG92RXvxSTWv:4:WgWxqztrNooG92RXvxSTWv:3:CL:20:tag:CL_ACCUM:0": []
                }
            },
        )

    assert_that(exc.value.status_code).is_equal_to(404)


@pytest.mark.anyio
async def test_publish_all_revocations_for_rev_reg_id(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[CredentialExchange],
):
    faber_cred_ex_id = issue_alice_creds_and_revoke_unpublished[0].credential_id[3:]
    response = (
        await faber_client.get(
            f"{CREDENTIALS_BASE_PATH}/revocation/record"
            + "?credential_exchange_id="
            + faber_cred_ex_id
        )
    ).json()

    rev_reg_id = response["rev_reg_id"]

    await faber_client.post(
        f"{CREDENTIALS_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {rev_reg_id: []}},
    )

    for cred in issue_alice_creds_and_revoke_unpublished:
        rev_record = (
            await faber_client.get(
                f"{CREDENTIALS_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_id[3:]
            )
        ).json()

        assert rev_record["state"] == "revoked"


@pytest.mark.anyio
async def test_publish_all_revocations_no_payload(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[CredentialExchange],
):
    await faber_client.post(
        f"{CREDENTIALS_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {}},
    )

    for cred in issue_alice_creds_and_revoke_unpublished:
        rev_record = (
            await faber_client.get(
                f"{CREDENTIALS_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_id[3:]
            )
        ).json()

        assert rev_record["state"] == "revoked"


@pytest.mark.anyio
async def test_publish_one_revocation(
    faber_client: RichAsyncClient,
    issue_alice_creds_and_revoke_unpublished: List[CredentialExchange],
):
    faber_cred_ex_id = issue_alice_creds_and_revoke_unpublished[0].credential_id[3:]
    response = (
        await faber_client.get(
            f"{CREDENTIALS_BASE_PATH}/revocation/record"
            + "?credential_exchange_id="
            + faber_cred_ex_id
        )
    ).json()

    rev_reg_id = response["rev_reg_id"]
    cred_rev_id = response["cred_rev_id"]
    await faber_client.post(
        f"{CREDENTIALS_BASE_PATH}/publish-revocations",
        json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
    )

    for cred in issue_alice_creds_and_revoke_unpublished:
        rev_record = (
            await faber_client.get(
                f"{CREDENTIALS_BASE_PATH}/revocation/record"
                + "?credential_exchange_id="
                + cred.credential_id[3:]
            )
        ).json()

        if rev_record["cred_rev_id"] == cred_rev_id:
            assert rev_record["state"] == "revoked"
        else:
            assert rev_record["state"] == "issued"

    # Test for cred_rev_id not pending
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": {rev_reg_id: [cred_rev_id]}},
        )

    assert_that(exc.value.status_code).is_equal_to(404)


@pytest.mark.anyio
async def test_publish_revocations_bad_payload(
    faber_client: RichAsyncClient,
):
    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": "bad"},
        )

    assert_that(exc.value.status_code).is_equal_to(422)

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/publish-revocations",
            json={"revocation_registry_credential_map": {"bad": "bad"}},
        )

    assert_that(exc.value.status_code).is_equal_to(422)

    with pytest.raises(HTTPException) as exc:
        await faber_client.post(
            f"{CREDENTIALS_BASE_PATH}/publish-revocations",
            json={
                "revocation_registry_credential_map": {
                    "WgWxqztrNooG92RXvxSTWv:4:WgWxqztrNooG92RXvxSTWv:3:CL:20:tag:CL_ACCUM:0": []
                }
            },
        )

    assert_that(exc.value.status_code).is_equal_to(404)
